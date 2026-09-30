from datetime import date

STATUS_WEIGHTS = {
    "Follow-up Needed": 4,
    "Interested": 3,
    "New": 2,
    "Closed": 0,
}

INTEREST_WEIGHTS = {
    "High": 3,
    "Medium": 2,
    "Low": 1,
}


def compute_priority_score(next_followup, status: str, interest_level: str) -> float:
    """
    Score a lead from 0–10 based on urgency and interest.
    Higher = needs attention sooner.

    Components:
      - Overdue penalty:  +4 if overdue, +2 if due today, +1 if due within 3 days
      - Status weight:    0–4
      - Interest weight:  1–3
    Max raw score = 4 + 4 + 3 = 11, normalised to 10.
    """
    today = date.today()
    urgency = 0

    if next_followup:
        delta = (next_followup - today).days
        if delta < 0:
            urgency = 4        # overdue
        elif delta == 0:
            urgency = 2        # due today
        elif delta <= 3:
            urgency = 1        # coming up soon

    status_score = STATUS_WEIGHTS.get(status, 1) # just to handle empty status
    interest_score = INTEREST_WEIGHTS.get(interest_level, 1)

    raw = urgency + status_score + interest_score
    normalised = round(min(raw / 11 * 10, 10), 1) # it will reach max 10 so i used min her
    return normalised


def score_label(score: float) -> str:
    if score >= 8:
        return "🔴 Hot"
    elif score >= 5:
        return "🟡 Warm"
    else:
        return "🟢 Cool"