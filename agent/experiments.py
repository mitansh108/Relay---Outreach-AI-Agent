"""Small, predeclared two-arm message experiments.

Assignment is stable for a contact and experiment. Analysis is deliberately
conservative: no winner before the scheduled end, response window, sample
floor, and a two-sided 95% test with enough events for a normal approximation.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta
from typing import Any


VALUES = {
    "tone": {"friendly", "professional"},
    "length": {"short", "detailed"},
    "cta": {"soft", "direct"},
}


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def validate_experiment(config: dict[str, Any]) -> dict[str, Any]:
    """Return normalized config, or raise ValueError for an unsafe design."""
    try:
        test_id = str(config["id"]).strip()
        variable = str(config["variable"]).strip().lower()
        start = _date(config["start_date"])
        end = _date(config["end_date"])
        variants = config["variants"]
        minimum = int(config.get("min_per_variant", 100))
        response_days = int(config.get("response_window_days", 7))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Experiment requires id, variable, dates, and two variants.") from exc
    if not test_id or len(test_id) > 100:
        raise ValueError("Experiment id must contain 1–100 characters.")
    if variable not in VALUES:
        raise ValueError("Experiment must change exactly one supported variable: tone, length, or cta.")
    if end < start + timedelta(days=13):
        raise ValueError("Experiment must run for at least 14 calendar days.")
    if minimum < 100:
        raise ValueError("At least 100 sent messages per variant are required for analysis.")
    if response_days < 1 or response_days > 30:
        raise ValueError("Response window must be 1–30 days.")
    if not isinstance(variants, list) or len(variants) != 2:
        raise ValueError("Exactly two variants are required.")
    normalized = []
    for variant in variants:
        if not isinstance(variant, dict) or set(variant) != {"id", "value", "weight"}:
            raise ValueError("Each variant needs only id, value, and weight.")
        variant_id = str(variant["id"]).strip()
        value = str(variant["value"]).strip().lower()
        try:
            weight = int(variant["weight"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Variant weights must be integers.") from exc
        if not variant_id or value not in VALUES[variable] or weight < 1 or weight > 99:
            raise ValueError("Variant id, value, or weight is invalid.")
        normalized.append({"id": variant_id, "value": value, "weight": weight})
    if len({v["id"] for v in normalized}) != 2 or len({v["value"] for v in normalized}) != 2:
        raise ValueError("Variant ids and values must differ.")
    if sum(v["weight"] for v in normalized) != 100:
        raise ValueError("Variant weights must total 100.")
    return {
        "id": test_id,
        "variable": variable,
        "start_date": start,
        "end_date": end,
        "variants": normalized,
        "min_per_variant": minimum,
        "response_window_days": response_days,
    }


def assign_variant(contact_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Map one stable contact ID to a weighted bucket without stored randomness."""
    test = validate_experiment(config)
    if not str(contact_id).strip():
        raise ValueError("Stable contact_id is required for experiment assignment.")
    digest = hashlib.sha256(f"{test['id']}\x00{contact_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % 10000
    threshold = test["variants"][0]["weight"] * 100
    chosen = test["variants"][0] if bucket < threshold else test["variants"][1]
    return {"test_id": test["id"], "variant_id": chosen["id"], "variable": test["variable"], "value": chosen["value"]}


def variant_instruction(assignment: dict[str, str]) -> str:
    """Change one writing dimension while asking the model to hold others fixed."""
    variable, value = assignment["variable"], assignment["value"]
    if value not in VALUES.get(variable, set()):
        raise ValueError("Unsupported experiment assignment.")
    instructions = {
        "tone": {
            "friendly": "Use a friendly, conversational tone. Keep length and call to action unchanged.",
            "professional": "Use a professional, concise tone. Keep length and call to action unchanged.",
        },
        "length": {
            "short": "Keep the email under 65 words. Keep tone and call to action unchanged.",
            "detailed": "Write 85–110 words. Keep tone and call to action unchanged.",
        },
        "cta": {
            "soft": "End with a low-pressure, open invitation. Keep tone and length unchanged.",
            "direct": "End with a clear request to schedule a specific next step. Keep tone and length unchanged.",
        },
    }
    return instructions[variable][value]


def summarize_experiment(
    config: dict[str, Any], outcomes: list[dict[str, Any]], *, now: date | None = None
) -> dict[str, Any]:
    """Analyze observed sends and replies; return winner only after all gates."""
    test = validate_experiment(config)
    today = now or date.today()
    by_id = {v["id"]: {"variant_id": v["id"], "sent": 0, "replied": 0, "opted_out": 0} for v in test["variants"]}
    seen: set[str] = set()
    for outcome in outcomes:
        try:
            if outcome.get("test_id") != test["id"] or outcome.get("variant_id") not in by_id:
                continue
            sent = _date(outcome["sent_at"])
            contact_id = str(outcome["contact_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if not contact_id or contact_id in seen or sent < test["start_date"] or sent > test["end_date"]:
            continue
        seen.add(contact_id)
        row = by_id[outcome["variant_id"]]
        row["sent"] += 1
        row["replied"] += bool(outcome.get("replied"))
        row["opted_out"] += bool(outcome.get("opted_out"))
    rows = list(by_id.values())
    for row in rows:
        row["reply_rate"] = row["replied"] / row["sent"] if row["sent"] else 0.0
        row["opt_out_rate"] = row["opted_out"] / row["sent"] if row["sent"] else 0.0
    result: dict[str, Any] = {"test_id": test["id"], "variants": rows, "status": "collecting", "winner": None, "z_score": None}
    if today <= test["end_date"] + timedelta(days=test["response_window_days"]):
        result["reason"] = "Experiment or response window is still open."
        return result
    if any(row["sent"] < test["min_per_variant"] for row in rows):
        result.update(status="insufficient_data", reason="Predeclared sample target was not reached in both variants.")
        return result
    a, b = rows
    if any(min(row["replied"], row["sent"] - row["replied"]) < 5 for row in rows):
        result.update(status="inconclusive", reason="Too few replies or non-replies for the normal approximation.")
        return result
    pooled = (a["replied"] + b["replied"]) / (a["sent"] + b["sent"])
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / a["sent"] + 1 / b["sent"]))
    z_score = (b["reply_rate"] - a["reply_rate"]) / standard_error
    result["z_score"] = z_score
    if abs(z_score) < 1.96:
        result.update(status="inconclusive", reason="Difference did not reach the predeclared 95% threshold.")
        return result
    winner = b if z_score > 0 else a
    loser = a if z_score > 0 else b
    if winner["opt_out_rate"] > loser["opt_out_rate"]:
        result.update(status="guardrail_review", reason="Higher reply rate came with a higher opt-out rate; review before rollout.")
        return result
    result.update(status="winner", winner=winner["variant_id"], reason="Sample, duration, response window, significance, and opt-out gates passed.")
    return result
