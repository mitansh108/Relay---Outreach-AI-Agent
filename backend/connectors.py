"""OAuth and provider operations. Tokens are encrypted before persistence."""
import base64
import hashlib
import html
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select

from .models import Connection, OAuthCredential, OAuthPending, now


PROVIDERS = {
    "hubspot": {
        "authorize": "https://app.hubspot.com/oauth/authorize",
        "token": "https://api.hubapi.com/oauth/v1/token",
        "scopes": "crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read",
        "client_id_env": "HUBSPOT_CLIENT_ID", "client_secret_env": "HUBSPOT_CLIENT_SECRET",
    },
    "gmail": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scopes": "https://www.googleapis.com/auth/gmail.send",
        "client_id_env": "GOOGLE_CLIENT_ID", "client_secret_env": "GOOGLE_CLIENT_SECRET",
    },
}


def cipher():
    key = os.getenv("COPILOT_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Set COPILOT_ENCRYPTION_KEY before connecting an account")
    return Fernet(key.encode())


def configured(provider):
    spec = PROVIDERS[provider]
    return bool(os.getenv(spec["client_id_env"]) and os.getenv(spec["client_secret_env"]) and os.getenv("COPILOT_ENCRYPTION_KEY"))


def redirect_uri(provider):
    base = os.getenv("COPILOT_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/api/oauth/{provider}/callback"


def authorization_url(db, provider):
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    if not configured(provider):
        raise ValueError(f"{provider} OAuth credentials and encryption key are not configured")
    spec = PROVIDERS[provider]
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64) if provider == "gmail" else None
    db.add(OAuthPending(state=state, provider=provider, code_verifier=verifier,
                        expires_at=now() + timedelta(minutes=10)))
    db.commit()
    params = {"client_id": os.environ[spec["client_id_env"]], "redirect_uri": redirect_uri(provider),
              "scope": spec["scopes"], "response_type": "code", "state": state}
    if provider == "gmail":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params.update(access_type="offline", prompt="consent", code_challenge=challenge, code_challenge_method="S256")
    return f"{spec['authorize']}?{urlencode(params)}"


def exchange_code(db, provider, state, code):
    pending = db.get(OAuthPending, state)
    if not pending or pending.provider != provider or pending.expires_at.replace(tzinfo=timezone.utc) < now():
        raise ValueError("OAuth state is invalid or expired")
    db.delete(pending)
    db.commit()
    spec = PROVIDERS[provider]
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(provider),
            "client_id": os.environ[spec["client_id_env"]], "client_secret": os.environ[spec["client_secret_env"]]}
    if pending.code_verifier:
        data["code_verifier"] = pending.code_verifier
    with httpx.Client(timeout=20) as client:
        response = client.post(spec["token"], data=data)
        response.raise_for_status()
        tokens = response.json()
    save_tokens(db, provider, tokens)


def save_tokens(db, provider, tokens):
    f = cipher()
    old = db.get(OAuthCredential, provider)
    refresh = tokens.get("refresh_token")
    credential = old or OAuthCredential(provider=provider, encrypted_token="")
    credential.encrypted_token = f.encrypt(tokens["access_token"].encode()).decode()
    if refresh:
        credential.encrypted_refresh_token = f.encrypt(refresh.encode()).decode()
    credential.expires_at = now() + timedelta(seconds=max(int(tokens.get("expires_in", 3600)) - 60, 60))
    db.add(credential)
    connection = db.get(Connection, provider) or Connection(provider=provider)
    connection.status, connection.last_error = "connected", None
    db.add(connection)
    db.commit()


def access_token(db, provider):
    credential = db.get(OAuthCredential, provider)
    if not credential:
        raise ValueError(f"{provider} is not connected")
    f = cipher()
    if credential.expires_at and credential.expires_at.replace(tzinfo=timezone.utc) <= now():
        if not credential.encrypted_refresh_token:
            raise ValueError(f"{provider} token expired; reconnect the account")
        spec = PROVIDERS[provider]
        refresh = f.decrypt(credential.encrypted_refresh_token.encode()).decode()
        with httpx.Client(timeout=20) as client:
            response = client.post(spec["token"], data={
                "grant_type": "refresh_token", "refresh_token": refresh,
                "client_id": os.environ[spec["client_id_env"]], "client_secret": os.environ[spec["client_secret_env"]]})
            response.raise_for_status()
            save_tokens(db, provider, response.json())
        credential = db.get(OAuthCredential, provider)
    return f.decrypt(credential.encrypted_token.encode()).decode()


def fetch_hubspot_contacts(db):
    token = access_token(db, "hubspot")
    records, after = [], None
    with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {token}"}) as client:
        while True:
            params = {"limit": 100, "properties": "firstname,lastname,email,company,hs_lead_status", "associations": "companies,deals,notes"}
            if after:
                params["after"] = after
            response = client.get("https://api.hubapi.com/crm/objects/2026-03/contacts", params=params)
            response.raise_for_status()
            payload = response.json()
            for record in payload.get("results", []):
                context = []
                for associated_type, properties in (
                    ("companies", "name,domain,industry"),
                    ("deals", "dealname,dealstage,amount"),
                    ("notes", "hs_note_body,hs_timestamp"),
                ):
                    ids = (record.get("associations") or {}).get(associated_type, {}).get("results", [])[:3]
                    for association in ids:
                        try:
                            linked = client.get(f"https://api.hubapi.com/crm/objects/2026-03/{associated_type}/{association['id']}", params={"properties": properties})
                            linked.raise_for_status()
                            fields = linked.json().get("properties") or {}
                            if associated_type == "companies":
                                label = "Company: " + (fields.get("name") or "")
                            elif associated_type == "deals":
                                label = "Deal: " + (fields.get("dealname") or "") + "; stage: " + (fields.get("dealstage") or "unknown")
                            else:
                                note = html.unescape(re.sub(r"<[^>]+>", " ", fields.get("hs_note_body") or ""))
                                label = "Note: " + " ".join(note.split())[:500]
                            if label.strip(" :;"):
                                context.append(label)
                        except (httpx.HTTPError, KeyError):
                            continue
                record["_context"] = context
                records.append(record)
            after = (payload.get("paging") or {}).get("next", {}).get("after")
            if not after:
                break
    return records


def send_gmail(db, recipient, subject, body):
    token = access_token(db, "gmail")
    sender = os.getenv("GOOGLE_SENDER_EMAIL", "").strip()
    if not sender or "@" not in sender:
        raise ValueError("Set GOOGLE_SENDER_EMAIL to the connected Gmail account or verified send-as address")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
    with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {token}"}) as client:
        response = client.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", json={"raw": encoded})
        response.raise_for_status()
        return response.json()["id"]
