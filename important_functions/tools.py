import streamlit as st
from datetime import date
import pandas as pd
import uuid
from important_functions.scoring import compute_priority_score, score_label


def init_state():
    for k, v in {
        "df":            None,   # working DataFrame — only this user's data
        "file_name":     None,   # original filename so export keeps the same name
        "msg_log":       {},     # {_lead_id: [{"tone":..,"message":..,"ts":..}]}
        "last_file_key": None,   # prevent re-import
        "upload_key":    str(uuid.uuid4()),
        "session_thread_id": str(uuid.uuid4()),  # was causing issues while multiple persons were using so, yeah
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


def followup_bucket(val):
    try:
        d = pd.to_datetime(val).date() if val else None
    except Exception:
        d = None
    if not d:         return "No Date"
    today = date.today()
    if d < today:     return "Overdue"
    if d == today:    return "Due Today"
    return "Upcoming"


def enrich(df: pd.DataFrame) -> pd.DataFrame: #  ^^^
    """Normalising columns and recomputing priority + bucket on the whole DataFrame."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]  #^^^
    if "_lead_id" not in df.columns:
        df["_lead_id"] = None
    df["_lead_id"] = df["_lead_id"].apply(
        lambda value: str(value) if pd.notna(value) and str(value) else str(uuid.uuid4())
    )

    # Ensuring all expected columns exist if not we create them 
    for col in ["name", "contact", "company", "status", "interest_level", "notes"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["last_interaction", "next_followup"]:
        if col not in df.columns:
            df[col] = ""

    df["status"]         = df["status"].replace("", pd.NA).fillna("New")
    df["interest_level"] = df["interest_level"].replace("", pd.NA).fillna("Medium")
    df["notes"]          = df["notes"].fillna("")
    df["company"]        = df["company"].fillna("")
    df["name"]           = df["name"].fillna("").astype(str)
    df["contact"]        = df["contact"].fillna("").astype(str)
    df["last_interaction"] = df["last_interaction"].fillna("")
    df["next_followup"] = df["next_followup"].fillna("")

    followup_dates = pd.to_datetime(df["next_followup"], format="mixed", errors="coerce")
    df["priority_score"] = [
        compute_priority_score(value.date() if pd.notna(value) else None, status, interest)
        for value, status, interest in zip(followup_dates, df["status"], df["interest_level"])
    ]
    df["priority_label"] = df["priority_score"].apply(score_label) #it store colour rgy
    df["bucket"]         = df["next_followup"].apply(followup_bucket)
    return df.sort_values("priority_score", ascending=False).reset_index(drop=True)  #descending for top prior table in t1
