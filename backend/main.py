"""Single-workspace CRM Copilot API. Run: uvicorn backend.main:app --reload."""
import csv
import io
import json
import os
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from important_functions.scoring import compute_priority_score, score_label

from .db import Base, engine, get_db
from .models import Activity, Connection, Contact, Experiment, ExperimentAssignment, OAuthCredential, Recommendation, SendAttempt, now
from .connectors import PROVIDERS, authorization_url, configured, exchange_code, fetch_hubspot_contacts, send_gmail


app = FastAPI(title="CRM Outreach Copilot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("COPILOT_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def access(request: Request, authorization: str | None = Header(default=None)):
    """Optional password-protected hosted demo; localhost needs no setup."""
    token = os.getenv("COPILOT_ACCESS_TOKEN")
    # OAuth providers cannot attach our workspace bearer token to callbacks.
    # The one-time state is validated and consumed by exchange_code instead.
    if request.url.path.endswith("/callback"):
        return
    if token and authorization != f"Bearer {token}":
        raise HTTPException(401, "Workspace access token required")


api = FastAPI(dependencies=[Depends(access)])
app.mount("/api", api)


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()))


def parse_date(value: str | None):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def contact_dict(c: Contact):
    followup = parse_date(c.next_followup)
    score = compute_priority_score(followup, c.status, c.interest_level)
    days = (followup - date.today()).days if followup else None
    bucket = "Overdue" if days is not None and days < 0 else "Due Today" if days == 0 else "Upcoming" if days is not None else "Unscheduled"
    return {
        "id": c.id, "name": c.name, "contact": c.contact, "company": c.company,
        "status": c.status, "interest_level": c.interest_level, "notes": c.notes,
        "deal_context": c.deal_context, "last_interaction": c.last_interaction,
        "next_followup": c.next_followup, "do_not_contact": c.do_not_contact,
        "replied": c.replied, "source": c.source, "priority_score": score,
        "priority_label": score_label(score), "bucket": bucket,
    }


def rec_dict(r: Recommendation):
    return {
        "id": r.id, "contact_id": r.contact_id, "action": r.action,
        "reason": r.reason, "sources": json.loads(r.sources or "[]"),
        "status": r.status, "subject": r.subject, "body": r.body,
        "version": r.version, "eligible": r.action == "email",
        "model_id": r.model_id, "experiment_id": r.experiment_id,
        "variant_id": r.variant_id, "created_at": r.created_at.isoformat(),
    }


def activity_dict(a: Activity):
    return {"id": a.id, "contact_id": a.contact_id, "recommendation_id": a.recommendation_id,
            "kind": a.kind, "detail": a.detail, "created_at": a.created_at.isoformat()}


def send_dict(s: SendAttempt):
    return {"id": s.id, "recommendation_id": s.recommendation_id, "recipient": s.recipient,
            "draft_version": s.draft_version, "status": s.status, "provider_id": s.provider_id,
            "error": s.error, "created_at": s.created_at.isoformat()}


def log(db, contact_id, kind, detail="", recommendation_id=None):
    db.add(Activity(contact_id=contact_id, recommendation_id=recommendation_id, kind=kind, detail=detail))


def checkpoint_path():
    return os.getenv("COPILOT_CHECKPOINT_DB", str(Path(__file__).resolve().parent / "checkpoints.sqlite"))


@contextmanager
def graph_for(recommendation_id: str, send_hook=None):
    from agent.copilot import build_copilot_graph
    with SqliteSaver.from_conn_string(checkpoint_path()) as saver:
        graph = build_copilot_graph(checkpointer=saver, send_hook=send_hook)
        yield graph, {"configurable": {"thread_id": recommendation_id}}


def start_review_checkpoint(recommendation_id: str, contact: dict, recommendation: dict):
    with graph_for(recommendation_id) as (graph, config):
        graph.invoke({"contact": contact, "recommendation": recommendation}, config)


def resume_review_checkpoint(recommendation_id: str, review: dict, send_hook=None):
    with graph_for(recommendation_id, send_hook=send_hook) as (graph, config):
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(409, "Review checkpoint is missing; generate a new recommendation")
        return graph.invoke(Command(resume=review), config)


def seed(db: Session):
    if db.scalar(select(func.count(Contact.id))):
        return
    path = Path(__file__).resolve().parents[1] / "sample_leads.csv"
    with path.open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            c = Contact(**{key: row.get(key, "") for key in (
                "name", "contact", "company", "status", "interest_level", "notes", "last_interaction", "next_followup"
            )}, source="demo", source_id=f"demo:{index}")
            db.add(c)
    for provider in ("hubspot", "gmail"):
        db.merge(Connection(provider=provider, status="disconnected"))
    db.commit()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(recommendations)")}
            for name in ("experiment_id", "variant_id"):
                if name not in columns:
                    connection.exec_driver_sql(f"ALTER TABLE recommendations ADD COLUMN {name} VARCHAR")
    with next(get_db()) as db:
        seed(db)


@api.get("/health")
def health():
    return {"status": "ok", "mode": os.getenv("COPILOT_MODE", "demo")}


@api.get("/summary")
def summary(db: Session = Depends(get_db)):
    contacts = db.scalars(select(Contact)).all()
    buckets = [contact_dict(c)["bucket"] for c in contacts]
    return {
        "total": len(contacts), "due_today": buckets.count("Due Today"),
        "overdue": buckets.count("Overdue"), "upcoming": buckets.count("Upcoming"),
        "pending_reviews": db.scalar(select(func.count(Recommendation.id)).where(Recommendation.status == "pending")) or 0,
        "sent": db.scalar(select(func.count(SendAttempt.id)).where(SendAttempt.status == "sent")) or 0,
        "simulated": db.scalar(select(func.count(SendAttempt.id)).where(SendAttempt.status == "simulated")) or 0,
    }


@api.get("/contacts")
def list_contacts(q: str = "", status: str = "", bucket: str = "", db: Session = Depends(get_db)):
    stmt = select(Contact)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(or_(Contact.name.ilike(needle), Contact.contact.ilike(needle), Contact.company.ilike(needle), Contact.notes.ilike(needle)))
    if status:
        stmt = stmt.where(Contact.status == status)
    items = [contact_dict(c) for c in db.scalars(stmt).all()]
    if bucket:
        items = [c for c in items if c["bucket"] == bucket]
    items.sort(key=lambda c: (-c["priority_score"], c["name"]))
    return {"items": items, "total": len(items)}


@api.get("/contacts/{contact_id}")
def get_contact(contact_id: str, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c:
        raise HTTPException(404, "Contact not found")
    result = contact_dict(c)
    result["activities"] = [activity_dict(a) for a in db.scalars(select(Activity).where(Activity.contact_id == contact_id).order_by(Activity.created_at.desc())).all()]
    result["recommendations"] = [rec_dict(r) for r in db.scalars(select(Recommendation).where(Recommendation.contact_id == contact_id).order_by(Recommendation.created_at.desc())).all()]
    return result


class ContactUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    company: str | None = None
    status: str | None = None
    interest_level: str | None = None
    notes: str | None = None
    next_followup: str | None = None
    replied: bool | None = None
    do_not_contact: bool | None = None


@api.patch("/contacts/{contact_id}")
def update_contact(contact_id: str, changes: ContactUpdate, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c:
        raise HTTPException(404, "Contact not found")
    data = changes.model_dump(exclude_unset=True)
    if c.source == "hubspot" and set(data) - {"next_followup", "replied", "do_not_contact"}:
        raise HTTPException(409, "HubSpot CRM fields are read-only")
    if "contact" in data and not valid_email(data["contact"]):
        raise HTTPException(422, "Enter a valid email address")
    if "next_followup" in data and data["next_followup"] and not parse_date(data["next_followup"]):
        raise HTTPException(422, "Use YYYY-MM-DD for next_followup")
    for key, value in data.items():
        setattr(c, key, value)
    if data.get("replied"):
        log(db, c.id, "replied", "Marked replied by user")
        for assignment in db.scalars(select(ExperimentAssignment).where(ExperimentAssignment.contact_id == c.id, ExperimentAssignment.exposed_at.is_not(None))):
            assignment.replied_at = assignment.replied_at or now()
    if data.get("do_not_contact"):
        for assignment in db.scalars(select(ExperimentAssignment).where(ExperimentAssignment.contact_id == c.id, ExperimentAssignment.exposed_at.is_not(None))):
            assignment.opted_out_at = assignment.opted_out_at or now()
    else:
        log(db, c.id, "contact_updated", ", ".join(data))
    db.commit()
    return contact_dict(c)


@api.post("/contacts/{contact_id}/replied")
def mark_replied(contact_id: str, db: Session = Depends(get_db)):
    return update_contact(contact_id, ContactUpdate(replied=True), db)


def fallback_recommend(c: dict):
    """Safe deterministic demo path when the optional agent is unavailable."""
    sources = ["status", "next_followup"]
    if c["do_not_contact"] or c["replied"] or c["status"] == "Closed":
        return {"action": "no_action", "reason": "This contact is closed, replied, or marked do not contact.", "sources": sources, "draft": None}
    if not valid_email(c["contact"]):
        return {"action": "call_task", "reason": "A valid email address is needed before drafting.", "sources": ["contact"], "draft": None}
    if c["bucket"] == "Upcoming":
        return {"action": "wait", "reason": f"The follow-up is scheduled for {c['next_followup']}.", "sources": ["next_followup"], "draft": None}
    if not c["notes"].strip():
        return {"action": "call_task", "reason": "Add context before sending a personalized email.", "sources": ["notes"], "draft": None}
    first = c["name"].split()[0]
    body = f"Hi {first},\n\nI wanted to reconnect about {c['notes'].rstrip('.')}. Would a quick conversation this week be useful?\n\nBest,"
    return {"action": "email", "reason": "Follow-up is due and the contact notes provide context for a personal message.", "sources": ["next_followup", "notes"], "draft": {"subject": f"Following up with {first}", "body": body}}


@api.post("/recommendations/{contact_id}")
def recommend_contact(contact_id: str, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c:
        raise HTTPException(404, "Contact not found")
    prior_send = db.scalar(select(SendAttempt).join(Recommendation, SendAttempt.recommendation_id == Recommendation.id).where(
        Recommendation.contact_id == c.id, SendAttempt.status.in_(["sent", "simulated"])).order_by(SendAttempt.created_at.desc()))
    cd = contact_dict(c)
    if prior_send and prior_send.created_at.replace(tzinfo=timezone.utc) > now() - timedelta(days=2):
        result = {"action": "no_action", "reason": "A message was sent to this contact in the past two days.", "sources": ["activity"], "draft": None}
    else:
        try:
            from agent.copilot import recommend
            active = db.scalar(select(Experiment).where(Experiment.status == "active").order_by(Experiment.created_at.desc()))
            experiment = json.loads(active.config) if active else None
            if prior_send:
                cd["last_sent_at"] = prior_send.created_at.isoformat()
            result = recommend(cd, context={"recent_activity": c.deal_context}, experiment=experiment, contact_id=c.id)
        except ImportError:
            result = fallback_recommend(cd)
    draft = result.get("draft") or {}
    r = Recommendation(contact_id=c.id, action=result["action"], reason=result["reason"],
                       sources=json.dumps(result.get("sources") or []), subject=draft.get("subject"),
                       body=draft.get("body"), model_id=result.get("model_id", "rules-demo-v1"),
                       experiment_id=(result.get("experiment") or {}).get("test_id"),
                       variant_id=(result.get("experiment") or {}).get("variant_id"))
    db.add(r)
    db.flush()
    if r.experiment_id and r.variant_id:
        assignment = db.scalar(select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == r.experiment_id, ExperimentAssignment.contact_id == c.id))
        if not assignment:
            db.add(ExperimentAssignment(experiment_id=r.experiment_id, contact_id=c.id, variant_id=r.variant_id))
    log(db, c.id, "recommendation", r.reason, r.id)
    db.commit()
    start_review_checkpoint(r.id, cd, result)
    return rec_dict(r)


@api.get("/recommendations")
def recommendations(status: str = "", db: Session = Depends(get_db)):
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc())
    if status:
        stmt = stmt.where(Recommendation.status == status)
    items = [rec_dict(r) for r in db.scalars(stmt).all()]
    return {"items": items, "total": len(items)}


@api.get("/recommendations/{recommendation_id}")
def recommendation(recommendation_id: str, db: Session = Depends(get_db)):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    return rec_dict(r)


class DraftChange(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


@api.patch("/recommendations/{recommendation_id}/draft")
def edit_draft(recommendation_id: str, data: DraftChange, db: Session = Depends(get_db)):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    if r.action != "email" or r.status in {"sent", "simulated", "skipped"}:
        raise HTTPException(409, "Draft cannot be edited")
    r.subject, r.body, r.version = data.subject.strip(), data.body.strip(), r.version + 1
    r.status, r.approved_version, r.approved_recipient = "pending", None, None
    log(db, r.contact_id, "draft_edited", f"Version {r.version}", r.id)
    db.commit()
    return rec_dict(r)


@api.post("/reviews/{recommendation_id}/approve")
def approve(recommendation_id: str, db: Session = Depends(get_db)):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    c = db.get(Contact, r.contact_id)
    if r.action != "email" or r.status not in {"pending", "approved"} or not r.subject or not r.body:
        raise HTTPException(409, "Only a complete email draft can be approved")
    if c.replied or c.do_not_contact or c.status == "Closed" or not valid_email(c.contact):
        raise HTTPException(409, "Contact is no longer eligible for email")
    r.status, r.approved_version, r.approved_recipient = "approved", r.version, c.contact
    log(db, c.id, "approved", f"Approved version {r.version} for {c.contact}", r.id)
    db.commit()
    return rec_dict(r)


@api.post("/reviews/{recommendation_id}/skip")
def skip(recommendation_id: str, db: Session = Depends(get_db)):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    if r.status in {"sent", "simulated"}:
        raise HTTPException(409, "Already sent")
    r.status = "skipped"
    log(db, r.contact_id, "skipped", "Skipped by user", r.id)
    db.commit()
    resume_review_checkpoint(r.id, {"approved": False})
    return rec_dict(r)


def execute_approved_send(recommendation_id: str, db: Session):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    c = db.get(Contact, r.contact_id)
    existing = db.scalar(select(SendAttempt).where(SendAttempt.recommendation_id == r.id))
    if existing:
        return send_dict(existing)
    if r.status != "approved" or r.approved_version != r.version or r.approved_recipient != c.contact:
        raise HTTPException(409, "Approve the current draft and recipient first")
    if c.replied or c.do_not_contact or c.status == "Closed" or not valid_email(c.contact):
        raise HTTPException(409, "Contact is no longer eligible for email")
    live = os.getenv("COPILOT_MODE", "demo") == "live" and c.source != "demo"
    if live:
        gmail = db.get(Connection, "gmail")
        if not gmail or gmail.status != "connected":
            raise HTTPException(409, "Connect Gmail before sending")
        if not os.getenv("GOOGLE_SENDER_EMAIL"):
            raise HTTPException(409, "Set GOOGLE_SENDER_EMAIL before sending")
    # Reserve before provider invocation. A repeated request returns this
    # attempt, even after an uncertain provider error, instead of retrying.
    attempt = SendAttempt(recommendation_id=r.id, recipient=c.contact, draft_version=r.version,
                          status="reserved")
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return send_dict(db.scalar(select(SendAttempt).where(SendAttempt.recommendation_id == r.id)))
    if live:
        try:
            attempt.provider_id = send_gmail(db, c.contact, r.subject, r.body)
            attempt.status = "sent"
        except Exception as exc:
            attempt.status = "failed"
            attempt.error = f"Gmail send was not confirmed: {type(exc).__name__}. Check Gmail before deciding whether to send another message."
    else:
        attempt.status, attempt.provider_id = "simulated", f"demo-{uuid4()}"
    r.status = attempt.status
    if r.experiment_id and attempt.status in {"sent", "simulated"}:
        assignment = db.scalar(select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == r.experiment_id, ExperimentAssignment.contact_id == c.id))
        if assignment and not assignment.exposed_at:
            assignment.exposed_at = now()
    log(db, c.id, "sent" if attempt.status == "sent" else "send_failed" if attempt.status == "failed" else "simulated_send",
        f"{attempt.status.title()} message to {c.contact}", r.id)
    db.commit()
    return send_dict(attempt)


@api.post("/sends/{recommendation_id}")
def send(recommendation_id: str, db: Session = Depends(get_db)):
    r = db.get(Recommendation, recommendation_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    existing = db.scalar(select(SendAttempt).where(SendAttempt.recommendation_id == r.id))
    if existing:
        return send_dict(existing)
    c = db.get(Contact, r.contact_id)
    if r.status != "approved" or r.approved_version != r.version or r.approved_recipient != c.contact:
        raise HTTPException(409, "Approve the current draft and recipient first")
    from agent.copilot import draft_fingerprint
    fingerprint = draft_fingerprint(c.contact, r.subject, r.body)

    def hook(payload, idempotency_key):
        if idempotency_key != fingerprint or payload["to"] != c.contact:
            raise HTTPException(409, "Approved draft changed before send")
        return execute_approved_send(recommendation_id, db)

    outcome = resume_review_checkpoint(recommendation_id, {
        "approved": True, "subject": r.subject, "body": r.body, "fingerprint": fingerprint,
    }, send_hook=hook)
    result = outcome.get("result") or {}
    if result.get("status") in {"rejected", "skipped"}:
        raise HTTPException(409, result.get("error") or "Review was not approved")
    attempt = db.scalar(select(SendAttempt).where(SendAttempt.recommendation_id == r.id))
    if not attempt:
        raise HTTPException(500, "Send result was not recorded")
    return send_dict(attempt)


@api.post("/contacts/{contact_id}/converted")
def mark_converted(contact_id: str, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c:
        raise HTTPException(404, "Contact not found")
    count = 0
    for assignment in db.scalars(select(ExperimentAssignment).where(ExperimentAssignment.contact_id == c.id, ExperimentAssignment.exposed_at.is_not(None))):
        if not assignment.converted_at:
            assignment.converted_at = now()
            count += 1
    log(db, c.id, "converted", "Marked converted by user")
    db.commit()
    return {"contact_id": c.id, "recorded": count}


class ExperimentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hypothesis: str = Field(default="", max_length=1000)
    variable: str
    variants: list[dict]
    start_date: str
    end_date: str
    min_per_variant: int = 100
    response_window_days: int = 7


@api.post("/experiments")
def create_experiment(payload: ExperimentInput, db: Session = Depends(get_db)):
    from agent.experiments import validate_experiment
    if db.scalar(select(Experiment).where(Experiment.status == "active")):
        raise HTTPException(409, "Pause the active experiment first")
    config = payload.model_dump(exclude={"name"})
    config["id"] = str(uuid4())
    try:
        validate_experiment(config)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    experiment = Experiment(id=config["id"], name=payload.name, config=json.dumps(config), status="active")
    db.add(experiment)
    db.commit()
    return {"id": experiment.id, "name": experiment.name, "status": experiment.status, "config": config}


@api.get("/experiments")
def list_experiments(db: Session = Depends(get_db)):
    return {"items": [{"id": e.id, "name": e.name, "status": e.status, "config": json.loads(e.config)} for e in db.scalars(select(Experiment).order_by(Experiment.created_at.desc())).all()]}


@api.post("/experiments/{experiment_id}/pause")
def pause_experiment(experiment_id: str, db: Session = Depends(get_db)):
    e = db.get(Experiment, experiment_id)
    if not e:
        raise HTTPException(404, "Experiment not found")
    e.status = "paused"
    db.commit()
    return {"id": e.id, "status": e.status}


@api.post("/experiments/{experiment_id}/start")
def start_experiment(experiment_id: str, db: Session = Depends(get_db)):
    e = db.get(Experiment, experiment_id)
    if not e:
        raise HTTPException(404, "Experiment not found")
    active = db.scalar(select(Experiment).where(Experiment.status == "active", Experiment.id != experiment_id))
    if active:
        raise HTTPException(409, "Pause the active experiment first")
    e.status = "active"
    db.commit()
    return {"id": e.id, "status": e.status}


@api.get("/experiments/{experiment_id}/results")
def experiment_results(experiment_id: str, db: Session = Depends(get_db)):
    from agent.experiments import summarize_experiment
    e = db.get(Experiment, experiment_id)
    if not e:
        raise HTTPException(404, "Experiment not found")
    assignments = db.scalars(select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == e.id)).all()
    outcomes = [{"test_id": e.id, "contact_id": a.contact_id, "variant_id": a.variant_id,
                 "sent_at": a.exposed_at.isoformat(), "replied": bool(a.replied_at),
                 "converted": bool(a.converted_at), "opted_out": bool(a.opted_out_at)}
                for a in assignments if a.exposed_at]
    result = summarize_experiment(json.loads(e.config), outcomes)
    converted = {v["variant_id"]: 0 for v in result["variants"]}
    for outcome in outcomes:
        if outcome["converted"] and outcome["variant_id"] in converted:
            converted[outcome["variant_id"]] += 1
    for variant in result["variants"]:
        variant["converted"] = converted[variant["variant_id"]]
    return result


@api.get("/activity")
def activity(contact_id: str = "", db: Session = Depends(get_db)):
    stmt = select(Activity).order_by(Activity.created_at.desc())
    if contact_id:
        stmt = stmt.where(Activity.contact_id == contact_id)
    items = [activity_dict(a) for a in db.scalars(stmt).all()]
    return {"items": items, "total": len(items)}


@api.get("/insights")
def insights(db: Session = Depends(get_db)):
    return {
        "contacts": db.scalar(select(func.count(Contact.id))) or 0,
        "recommendations": db.scalar(select(func.count(Recommendation.id))) or 0,
        "approved": db.scalar(select(func.count(Activity.id)).where(Activity.kind == "approved")) or 0,
        "skipped": db.scalar(select(func.count(Recommendation.id)).where(Recommendation.status == "skipped")) or 0,
        "pending": db.scalar(select(func.count(Recommendation.id)).where(Recommendation.status == "pending")) or 0,
        "simulated": db.scalar(select(func.count(SendAttempt.id)).where(SendAttempt.status == "simulated")) or 0,
        "sent": db.scalar(select(func.count(SendAttempt.id)).where(SendAttempt.status == "sent")) or 0,
        "failed": db.scalar(select(func.count(SendAttempt.id)).where(SendAttempt.status == "failed")) or 0,
    }


@api.get("/connections")
def connections(db: Session = Depends(get_db)):
    return {"items": [{"provider": c.provider, "status": c.status,
                       "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
                       "last_error": c.last_error, "sync_count": c.sync_count,
                       "configured": configured(c.provider)}
                      for c in db.scalars(select(Connection)).all()]}


@api.get("/oauth/{provider}/start")
def oauth_start(provider: str, db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    try:
        return {"authorization_url": authorization_url(db, provider)}
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.get("/oauth/{provider}/callback")
def oauth_callback(provider: str, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    if error:
        raise HTTPException(400, f"{provider} authorization was denied: {error}")
    if not state or not code:
        raise HTTPException(400, "OAuth callback is incomplete")
    try:
        exchange_code(db, provider, state, code)
    except Exception as exc:
        raise HTTPException(400, f"Could not connect {provider}: {type(exc).__name__}") from exc
    url = os.getenv("COPILOT_PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
    return RedirectResponse(f"{url}/connections?connected={provider}")


@api.post("/connections/{provider}/disconnect")
def disconnect(provider: str, db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    credential = db.get(OAuthCredential, provider)
    if credential:
        db.delete(credential)
    connection = db.get(Connection, provider) or Connection(provider=provider)
    connection.status, connection.last_error = "disconnected", None
    db.add(connection)
    db.commit()
    return {"provider": provider, "status": "disconnected"}


@api.post("/connections/hubspot/sync")
def sync_hubspot(db: Session = Depends(get_db)):
    connection = db.get(Connection, "hubspot")
    if not connection or connection.status != "connected":
        raise HTTPException(409, "Connect HubSpot first")
    try:
        records = fetch_hubspot_contacts(db)
        count = 0
        for record in records:
            props = record.get("properties") or {}
            email = (props.get("email") or "").strip().lower()
            if not valid_email(email):
                continue
            source_id = f"hubspot:{record['id']}"
            contact = db.scalar(select(Contact).where(Contact.source_id == source_id))
            if not contact:
                contact = Contact(source="hubspot", source_id=source_id)
                db.add(contact)
            contact.name = " ".join(filter(None, [props.get("firstname"), props.get("lastname")])).strip() or email
            contact.contact = email
            contact.company = props.get("company") or ""
            contact.status = props.get("hs_lead_status") or "New"
            contact.interest_level = contact.interest_level or "Medium"
            contact.deal_context = "\n".join(record.get("_context") or [])
            contact.notes = "\n".join(x for x in record.get("_context") or [] if x.startswith("Note:"))
            count += 1
        connection.last_sync_at, connection.last_error = now(), None
        connection.sync_count += count
        db.commit()
        return {"synced": count, "last_sync_at": connection.last_sync_at.isoformat()}
    except Exception as exc:
        db.rollback()
        connection = db.get(Connection, "hubspot")
        connection.last_error = f"Sync failed: {type(exc).__name__}"
        db.commit()
        raise HTTPException(502, connection.last_error) from exc


@api.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    for table in (SendAttempt, Activity, ExperimentAssignment, Recommendation, Experiment, Contact):
        db.query(table).delete()
    db.commit()
    seed(db)
    return summary(db)


class CsvImport(BaseModel):
    csv_text: str


def parse_csv(content: str, db: Session):
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or not {"name", "contact"}.issubset(set(reader.fieldnames)):
        raise HTTPException(422, "CSV requires name and contact columns")
    rows, errors, seen = [], [], set()
    known = {email.lower() for email in db.scalars(select(Contact.contact)).all()}
    for line, row in enumerate(reader, start=2):
        email = (row.get("contact") or "").strip().lower()
        name = (row.get("name") or "").strip()
        if not name or not valid_email(email):
            errors.append({"line": line, "reason": "Name or email is invalid"})
            continue
        if email in seen or email in known:
            errors.append({"line": line, "reason": "Duplicate email"})
            continue
        if row.get("next_followup") and not parse_date(row["next_followup"]):
            errors.append({"line": line, "reason": "Invalid next_followup date"})
            continue
        seen.add(email)
        rows.append({key: (row.get(key) or "").strip() for key in (
            "name", "contact", "company", "status", "interest_level", "notes", "last_interaction", "next_followup"
        )})
    return rows, errors


@api.post("/import/preview")
def preview_import(payload: CsvImport, db: Session = Depends(get_db)):
    rows, errors = parse_csv(payload.csv_text, db)
    return {"valid_rows": rows, "errors": errors, "count": len(rows)}


@api.post("/import/commit")
def commit_import(payload: CsvImport, db: Session = Depends(get_db)):
    rows, errors = parse_csv(payload.csv_text, db)
    for row in rows:
        db.add(Contact(**row, source="csv"))
    db.commit()
    return {"imported": len(rows), "errors": errors}


@api.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    output = io.StringIO()
    fields = ["name", "contact", "company", "status", "interest_level", "notes", "last_interaction", "next_followup"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for c in db.scalars(select(Contact)).all():
        writer.writerow({key: getattr(c, key) for key in fields})
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contacts.csv"})
