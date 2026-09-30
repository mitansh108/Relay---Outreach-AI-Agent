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
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete

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
    spec = PROVIDERS.get(provider)
    if not spec or not os.getenv(spec["client_id_env"]) or not os.getenv(spec["client_secret_env"]):
        return False
    try:
        cipher()
    except (ValueError, RuntimeError):
        return False
    return True


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
                        expires_at=now() + timedelta(minutes=10), user_id=db.info.get("user_id")))
    db.commit()
    params = {"client_id": os.environ[spec["client_id_env"]], "redirect_uri": redirect_uri(provider),
              "scope": spec["scopes"], "response_type": "code", "state": state}
    if provider == "gmail":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params.update(access_type="offline", prompt="consent", code_challenge=challenge, code_challenge_method="S256")
    return f"{spec['authorize']}?{urlencode(params)}"


def exchange_code(db, provider, state, code):
    if provider not in PROVIDERS or not code:
        raise ValueError("OAuth provider or code is invalid")
    pending = db.get(OAuthPending, state)
    if not pending or pending.provider != provider or pending.expires_at.replace(tzinfo=timezone.utc) < now():
        raise ValueError("OAuth state is invalid or expired")
    verifier = pending.code_verifier
    # Consume once in the database, including competing callback requests.
    consumed = db.execute(delete(OAuthPending).where(OAuthPending.state == state))
    db.commit()
    if consumed.rowcount != 1:
        raise ValueError("OAuth state has already been used")
    spec = PROVIDERS[provider]
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(provider),
            "client_id": os.environ[spec["client_id_env"]], "client_secret": os.environ[spec["client_secret_env"]]}
    if verifier:
        data["code_verifier"] = verifier
    with httpx.Client(timeout=20) as client:
        response = client.post(spec["token"], data=data)
        response.raise_for_status()
        tokens = response.json()
    save_tokens(db, provider, tokens)


def save_tokens(db, provider, tokens):
    if provider not in PROVIDERS or not isinstance(tokens.get("access_token"), str) or not tokens["access_token"].strip():
        raise ValueError("Provider did not return a usable access token; reconnect the account")
    lifetime = int(tokens.get("expires_in", 3600))
    if lifetime <= 0:
        raise ValueError("Provider returned an expired token; reconnect the account")
    f = cipher()
    old = db.get(OAuthCredential, provider)
    refresh = tokens.get("refresh_token")
    credential = old or OAuthCredential(provider=provider, encrypted_token="")
    credential.encrypted_token = f.encrypt(tokens["access_token"].encode()).decode()
    if refresh:
        credential.encrypted_refresh_token = f.encrypt(refresh.encode()).decode()
    credential.expires_at = now() + timedelta(seconds=max(lifetime - 60, 0))
    db.add(credential)
    connection = db.get(Connection, provider) or Connection(provider=provider)
    connection.status, connection.last_error = "connected", None
    db.add(connection)
    db.commit()


def access_token(db, provider):
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    credential = db.get(OAuthCredential, provider)
    if not credential:
        raise ValueError(f"{provider} is not connected")

    def fail(message, cause=None):
        connection = db.get(Connection, provider) or Connection(provider=provider)
        connection.last_error = message
        db.add(connection)
        db.commit()
        raise ValueError(message) from cause

    try:
        f = cipher()
        token = f.decrypt(credential.encrypted_token.encode()).decode()
    except (RuntimeError, ValueError, InvalidToken) as exc:
        fail(f"{provider.title()} credentials cannot be decrypted. Restore the workspace encryption key or reconnect the account.", exc)
    if credential.expires_at and credential.expires_at.replace(tzinfo=timezone.utc) <= now():
        if not credential.encrypted_refresh_token:
            fail(f"{provider.title()} token expired; reconnect the account.")
        spec = PROVIDERS[provider]
        try:
            refresh = f.decrypt(credential.encrypted_refresh_token.encode()).decode()
            with httpx.Client(timeout=20) as client:
                response = client.post(spec["token"], data={
                    "grant_type": "refresh_token", "refresh_token": refresh,
                    "client_id": os.environ[spec["client_id_env"]], "client_secret": os.environ[spec["client_secret_env"]]})
                response.raise_for_status()
                save_tokens(db, provider, response.json())
        except (httpx.HTTPError, ValueError, KeyError, InvalidToken) as exc:
            fail(f"{provider.title()} token refresh failed. Reconnect the account and try again.", exc)
        credential = db.get(OAuthCredential, provider)
        token = f.decrypt(credential.encrypted_token.encode()).decode()
    return token


def fetch_hubspot_contacts(db):
    token = access_token(db, "hubspot")
    records, after, visited = [], None, set()
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
                context_errors = 0
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
                            context_errors += 1
                            continue
                record["_context"] = context
                record["_context_errors"] = context_errors
                records.append(record)
            after = (payload.get("paging") or {}).get("next", {}).get("after")
            if not after:
                break
            if str(after) in visited:
                raise ValueError("HubSpot returned a repeated page cursor; sync again")
            visited.add(str(after))
    return records


def send_gmail(db, recipient, subject, body):
    token = access_token(db, "gmail")
    connection = db.get(Connection, "gmail") if db is not None else None
    sender = (connection.sender_email if connection else None) or (os.getenv("GOOGLE_SENDER_EMAIL", "").strip() if db is None or not db.info.get("user_id") else "")
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
