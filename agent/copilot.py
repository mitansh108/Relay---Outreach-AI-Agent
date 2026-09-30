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
    if status in {"unsubscribed", "do not contact"}:
        return False, "Contact is unsubscribed or marked do not contact."
    if status in {"closed", "closed won", "closed lost"} and not _day(contact.get("next_followup")):
        return False, "Closed contact has no scheduled follow-up."
    email = str(contact.get("email") or contact.get("contact") or "").strip()
    if not EMAIL_RE.fullmatch(email):
        return False, "Contact has no usable email address."
    last_sent = _day(contact.get("last_sent_at"))
    if last_sent and last_sent > today - timedelta(days=2):
        return False, "An email was sent too recently."
    return True, "Eligible for follow-up."


def _sources(contact: dict[str, Any], context: dict[str, Any]) -> list[dict[str, str]]:
    allowed = ("name", "company", "status", "interest_level", "notes", "last_interaction", "next_followup", "deal_context")
    refs = [{"field": key, "value": str(contact[key])} for key in allowed if contact.get(key) not in (None, "")]
    for key in ("deal_stage", "deal_name", "recent_activity"):
        if context.get(key) not in (None, ""):
            refs.append({"field": key, "value": str(context[key])})
    return refs


def _valid_refs(refs: Any, sources: list[dict[str, str]]) -> bool:
    """Model citations must identify existing facts, never newly invented facts."""
    return isinstance(refs, list) and bool(refs) and all(
        isinstance(ref, dict) and ref in sources for ref in refs
    )


def _grounded_text(text: str, sources: list[dict[str, str]]) -> bool:
    """Reject unsupported hard facts (amounts, dates, URLs, email addresses).

    This deliberately conservative guard complements exact citations and the
    model's grounding prompt. Human review remains required for semantic claims.
    """
    known = " ".join(source["value"] for source in sources).lower()
    pattern = r"https?://[^\s]+|[\w.+-]+@[\w.-]+|(?:[$€£]\s*)?\d[\d.,%:/-]*"
    tokens = re.findall(pattern, text.lower())
    known_tokens = set(re.findall(pattern, known))
    return all(token in known_tokens for token in tokens)


def _model_error(exc: Exception) -> str:
    # Do not expose provider exceptions: they may contain credentials or prompts.
    safe_codes = {
        "invalid_credentials": "Model credentials were rejected. Check the server model configuration.",
        "invalid_model": "The configured model is unavailable. Choose a supported model.",
        "rate_limited": "The model is busy. Try generation again later.",
    }
    return safe_codes.get(getattr(exc, "code", ""), "Model generation failed. A rule/template fallback was used; check model access and try again.")


def _sample_draft(contact: dict[str, Any], assignment: dict[str, str] | None = None) -> dict[str, str]:
    first = (str(contact.get("name") or "").split() or ["there"])[0]
    company = " ".join(str(contact.get("company") or "").split()) or "your team"
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

    Models implement ``recommend_action(contact, context)`` with exact ``sources``
    and ``generate(customer)`` returning subject, body and exact ``facts``.
    Invalid model output falls back to deterministic logic, visibly labeled.
    """
    context = context or {}
    today = now or date.today()
    sources = _sources(contact, context)
    metadata = {
        "model_id": "rules-demo-v1", "prompt_version": "bounded-copilot-v2",
        "generation_source": "rules", "model_status": "not_configured" if llm is None else "not_used",
        "decision_path": ["gather", "eligibility"],
        "inputs": {"contact": dict(contact), "context": dict(context)}, "outputs": {},
    }

    def fallback(message: str):
        metadata.update(model_status="fallback", fallback_reason=message, generation_error=message)
        metadata["decision_path"].append("model_fallback")

    allowed, rule_reason = eligibility(contact, now=today)
    if not allowed:
        return {"action": "no_action", "reason": rule_reason, "sources": sources, "draft": None, "eligible": False, **metadata}

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
    metadata["decision_path"].append(f"rules:{default_action}")
    if llm is not None and default_action in {"email", "call_task"} and hasattr(llm, "recommend_action"):
        try:
            proposed = llm.recommend_action(contact, context)
            if not isinstance(proposed, dict):
                raise ValueError("Invalid decision shape")
            candidate = proposed.get("action")
            # The model may be more conservative than the default, but cannot
            # draft an email when the deterministic context check ruled it out.
            if (isinstance(candidate, str) and candidate in VALID_ACTIONS
                    and (candidate != "email" or default_action == "email")
                    and isinstance(proposed.get("reason"), str) and proposed["reason"].strip()
                    and _valid_refs(proposed.get("sources"), sources)
                    and _grounded_text(proposed["reason"], sources)):
                action = candidate
                reason = proposed["reason"].strip()
                metadata.update(model_id=getattr(llm, "model_id", "configured-model"),
                                prompt_version=getattr(llm, "prompt_version", "bounded-copilot-v2"),
                                generation_source="model", model_status="ready")
                metadata["decision_path"].append(f"model:{candidate}")
                metadata["outputs"]["decision"] = proposed
            else:
                fallback("The model decision was invalid or had unsupported source facts. Rules were used.")
        except Exception as exc:
            fallback(_model_error(exc))

    assignment = None
    if action == "email" and experiment is not None:
        test = validate_experiment(experiment)
        if test["start_date"] <= today <= test["end_date"]:
            stable_id = contact_id or str(contact.get("id") or contact.get("contact_id") or "")
            assignment = assign_variant(stable_id, experiment)

    draft = None
    if action == "email":
        draft = _sample_draft(contact, assignment)
        metadata["generation_source"] = "template"
        metadata["model_id"] = "rules-demo-v1"
        if llm is not None:
            try:
                if assignment and hasattr(llm, "generate_with_variant"):
                    generated = llm.generate_with_variant(contact, variant_instruction(assignment))
                else:
                    generated = llm.generate(customer=contact)
                if (isinstance(generated, dict)
                        and all(isinstance(generated.get(key), str) and generated[key].strip() for key in ("subject", "body"))
                        and len(generated["subject"]) <= 200 and len(generated["body"]) <= 12000
                        and not any(char in generated["subject"] for char in "\r\n")
                        and _valid_refs(generated.get("facts"), sources)
                        and _grounded_text(generated["subject"] + "\n" + generated["body"], sources)):
                    draft = {"subject": generated["subject"].strip(), "body": generated["body"].strip()}
                    metadata.update(generation_source="model", model_id=getattr(llm, "model_id", "configured-model"),
                                    prompt_version=getattr(llm, "prompt_version", "bounded-copilot-v2"))
                    if metadata["model_status"] != "fallback":
                        metadata["model_status"] = "ready"
                    metadata["outputs"]["draft"] = generated
                    metadata["decision_path"].append("model_draft")
                else:
                    fallback("The model draft was invalid or contained unsupported source facts. A template was used.")
            except Exception as exc:
                fallback(_model_error(exc))
        metadata["decision_path"].append("human_review_required")
    result = {"action": action, "reason": reason, "sources": sources, "draft": draft, "eligible": True, **metadata}
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
        # The API has already persisted this draft. Regeneration here would
        # replace model output and experiment assignments before human review.
        if state.get("recommendation"):
            allowed, reason = eligibility(state["contact"])
            rec = dict(state["recommendation"])
            if not allowed:
                rec.update(action="no_action", reason=reason, eligible=False, draft=None)
            else:
                rec["eligible"] = True
            return {"recommendation": rec}
        return {"recommendation": recommend(state["contact"], state.get("context"), llm=llm, experiment=experiment)}

    def review(state: CopilotState) -> dict[str, Any]:
        rec = state["recommendation"]
        if rec["action"] != "email" or not rec["eligible"]:
            return {"review": {"approved": False}}
        response = interrupt({"contact": state["contact"], "recommendation": rec})
        return {"review": response if isinstance(response, dict) else {"approved": False}}

    def execute(state: CopilotState) -> dict[str, Any]:
        rec = state["recommendation"]
        review_data = state.get("review") or {}
        if rec["action"] != "email" or not rec["eligible"] or review_data.get("approved") is not True:
            return {"result": {"status": "skipped"}}
        recipient = str(state["contact"].get("email") or state["contact"].get("contact") or "").strip()
        subject = review_data.get("subject", rec["draft"]["subject"])
        body = review_data.get("body", rec["draft"]["body"])
        if (not isinstance(subject, str) or not isinstance(body, str) or not subject.strip() or not body.strip()
                or any(char in subject for char in "\r\n") or review_data.get("recipient", recipient) != recipient):
            return {"result": {"status": "rejected", "error": "Approved draft or recipient is invalid."}}
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
