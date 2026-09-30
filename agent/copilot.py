"""Bounded follow-up recommendations and a human-approved LangGraph workflow.

The caller owns persistence and delivery. In production, pass a persistent
checkpointer and a send_hook that atomically deduplicates by idempotency key.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent.experiments import assign_variant, validate_experiment, variant_instruction


Action = Literal["email", "call_task", "wait", "no_action"]
VALID_ACTIONS = {"email", "call_task", "wait", "no_action"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class CopilotState(TypedDict, total=False):
    contact: dict[str, Any]
    context: dict[str, Any]
    recommendation: dict[str, Any]
    review: dict[str, Any]
    result: dict[str, Any]


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "yes", "1"}


def eligibility(contact: dict[str, Any], *, now: date | None = None) -> tuple[bool, str]:
    """Apply non-model restrictions before any recommendation or send."""
    today = now or date.today()
    if _truthy(contact.get("do_not_contact")) or _truthy(contact.get("opted_out")):
        return False, "Contact is marked do not contact."
    if _truthy(contact.get("replied")):
        return False, "Contact has replied."
    status = str(contact.get("status", "")).strip().lower()
    if status in {"closed", "closed won", "closed lost", "unsubscribed"} and not contact.get("next_followup"):
        return False, "Closed contact has no scheduled follow-up."
    email = str(contact.get("email") or contact.get("contact") or "").strip()
    if not EMAIL_RE.fullmatch(email):
        return False, "Contact has no usable email address."
    last_sent = _day(contact.get("last_sent_at"))
    if last_sent and last_sent > today - timedelta(days=2):
        return False, "An email was sent too recently."
    return True, "Eligible for follow-up."


def _sources(contact: dict[str, Any], context: dict[str, Any]) -> list[dict[str, str]]:
    allowed = ("name", "company", "status", "interest_level", "notes", "last_interaction", "next_followup")
    refs = [{"field": key, "value": str(contact[key])} for key in allowed if contact.get(key) not in (None, "")]
    for key in ("deal_stage", "deal_name", "recent_activity"):
        if context.get(key) not in (None, ""):
            refs.append({"field": key, "value": str(context[key])})
    return refs


def _sample_draft(contact: dict[str, Any], assignment: dict[str, str] | None = None) -> dict[str, str]:
    first = str(contact.get("name") or "there").strip().split()[0]
    company = str(contact.get("company") or "your team").strip()
    variable = assignment["variable"] if assignment else None
    value = assignment["value"] if assignment else None
    greeting = f"Hello {first}," if variable == "tone" and value == "professional" else f"Hi {first},"
    if variable == "length" and value == "detailed":
        middle = f"I’m reaching out about the plans at {company}. If this is still a priority, I would be glad to hear where things stand and what information would be most helpful. We can focus the next conversation on your current questions and decide whether a further discussion makes sense."
    elif variable == "length" and value == "short":
        middle = f"Is it worth reconnecting about your plans at {company}?"
    else:
        middle = f"Would it be useful to reconnect about your plans at {company}?"
    cta = "Could we schedule a short call next week?" if variable == "cta" and value == "direct" else "Happy to find a time that works for you."
    return {
        "subject": f"Checking in about {company}",
        "body": f"{greeting}\n\n{middle} {cta}\n\nBest,",
    }


def recommend(
    contact: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    llm: Any = None,
    now: date | None = None,
    experiment: dict[str, Any] | None = None,
    contact_id: str | None = None,
) -> dict[str, Any]:
    """Return a bounded action and grounded draft; never perform an external action.

    An optional model may implement ``recommend_action(contact, context)`` and
    ``generate(customer)``. Invalid model actions fall back to deterministic logic.
    """
    context = context or {}
    today = now or date.today()
    sources = _sources(contact, context)
    allowed, rule_reason = eligibility(contact, now=today)
    if not allowed:
        return {"action": "no_action", "reason": rule_reason, "sources": sources, "draft": None, "eligible": False}

    due = _day(contact.get("next_followup"))
    if due and due > today:
        default_action: Action = "wait"
        reason = f"Follow-up is scheduled for {due.isoformat()}."
    elif not str(contact.get("notes") or context.get("recent_activity") or "").strip():
        default_action = "call_task"
        reason = "There is too little conversation context for a personalized email."
    else:
        default_action = "email"
        reason = "Follow-up is due and the contact has conversation context."

    action: Action = default_action
    if llm is not None and default_action in {"email", "call_task"} and hasattr(llm, "recommend_action"):
        try:
            proposed = llm.recommend_action(contact, context)
            candidate = proposed.get("action")
            # The model may be more conservative than the default, but cannot
            # draft an email when the deterministic context check ruled it out.
            if candidate in VALID_ACTIONS and (candidate != "email" or default_action == "email"):
                action = candidate
                reason = str(proposed.get("reason") or reason)
        except Exception:
            pass  # A model failure must not bypass eligibility or stop the queue.

    assignment = None
    if action == "email" and experiment is not None:
        test = validate_experiment(experiment)
        if test["start_date"] <= today <= test["end_date"]:
            stable_id = contact_id or str(contact.get("id") or contact.get("contact_id") or "")
            assignment = assign_variant(stable_id, experiment)

    draft = None
    if action == "email":
        draft = _sample_draft(contact, assignment)
        if llm is not None:
            try:
                if assignment and hasattr(llm, "generate_with_variant"):
                    generated = llm.generate_with_variant(contact, variant_instruction(assignment))
                else:
                    generated = llm.generate(customer=contact)
                if generated and str(generated).strip():
                    draft["body"] = str(generated).strip()
            except Exception:
                # Demo remains usable without an API key; the fallback makes no
                # claims beyond contact name and company.
                pass
    result = {"action": action, "reason": reason, "sources": sources, "draft": draft, "eligible": True}
    if assignment:
        result["experiment"] = assignment
    return result


def draft_fingerprint(recipient: str, subject: str, body: str) -> str:
    payload = json.dumps([recipient, subject, body], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_copilot_graph(
    *,
    llm: Any = None,
    send_hook: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
    checkpointer: Any = None,
    experiment: dict[str, Any] | None = None,
):
    """Compile the workflow. send_hook(payload, idempotency_key) must be idempotent.

    Pass a durable LangGraph checkpointer in deployed use. MemorySaver is only
    the local demo default.
    """
    def prepare(state: CopilotState) -> dict[str, Any]:
        return {"recommendation": recommend(state["contact"], state.get("context"), llm=llm, experiment=experiment)}

    def review(state: CopilotState) -> dict[str, Any]:
        rec = state["recommendation"]
        if rec["action"] != "email" or not rec["eligible"]:
            return {"review": {"approved": False}}
        response = interrupt({"contact": state["contact"], "recommendation": rec})
        return {"review": response}

    def execute(state: CopilotState) -> dict[str, Any]:
        rec = state["recommendation"]
        review_data = state.get("review") or {}
        if rec["action"] != "email" or not rec["eligible"] or not review_data.get("approved"):
            return {"result": {"status": "skipped"}}
        recipient = str(state["contact"].get("email") or state["contact"].get("contact") or "").strip()
        subject = str(review_data.get("subject") or rec["draft"]["subject"]).strip()
        body = str(review_data.get("body") or rec["draft"]["body"]).strip()
        expected = draft_fingerprint(recipient, subject, body)
        if review_data.get("fingerprint") != expected:
            return {"result": {"status": "rejected", "error": "Draft version was not approved."}}
        allowed, reason = eligibility(state["contact"])
        if not allowed:
            return {"result": {"status": "rejected", "error": reason}}
        if send_hook is None:
            return {"result": {"status": "simulated", "idempotency_key": expected}}
        payload = {"to": recipient, "subject": subject, "body": body, "contact": state["contact"]}
        return {"result": send_hook(payload, expected)}

    builder = StateGraph(CopilotState)
    builder.add_node("prepare", prepare)
    builder.add_node("review", review)
    builder.add_node("execute", execute)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "review")
    builder.add_edge("review", "execute")
    builder.add_edge("execute", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())
