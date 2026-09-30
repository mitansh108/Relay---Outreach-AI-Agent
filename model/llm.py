import json
import os

from groq import Groq

class FollowUpGenerator:

    MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    MAX_TOKENS = 300
    TEMPERATURE = 0.85

    SYSTEM_PROMPT = """You are a sharp, friendly sales rep writing follow-up emails on behalf of a small business.

Your emails should feel like they came from a real human — not a template. They should be warm, specific, and get to the point fast.

Rules you never break:
- Always address the person by their first name
- Only mention things that are actually in the notes — never invent details
- No filler openers like "I hope this email finds you well" or "I wanted to follow up"
- No bullet points — this is an email, write in natural sentences
- Sound like a person, not a software tool
- End with one clear next step"""

    def __init__(self, api_key):
        self._client = Groq(api_key=api_key)

    def _get_first_name(self, full_name: str) -> str:
        """Extract first name so we never say 'Hi John Smith'"""
        return full_name.strip().split()[0] if full_name.strip() else "there"

    def _build_prompt(self, customer: dict, tone: str = "Friendly") -> str:
        first_name = self._get_first_name(customer.get("name", ""))
        
        return f"""Write a {tone.lower()} follow-up email to {first_name}. The recipient works at {customer.get('company') or 'an unspecified company'}.


What you know about them:
- Status: {customer.get('status', '')}
- Interest level: {customer.get('interest_level', '')}
- Last spoke: {customer.get('last_interaction', 'unknown')}
- Notes from last conversation: {customer.get('notes', 'No notes available')}

Write the email body only — no subject line, no "Email body:" label.
Start directly with "Hi {first_name}," and keep it under 120 words.
Make it feel personal using the notes. If the notes mention something specific, reference it naturally.
End with one clear next step."""

    def generate(self, customer: dict, tone: str = "Friendly") -> str:
        if tone not in {"Professional", "Friendly", "Polite", "Persuasive"}:
            raise ValueError("Unsupported tone")
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(customer, tone)},
            ],
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
        )
        body = (response.choices[0].message.content or "").strip()
        if not body:
            raise ValueError("Groq returned an empty message")
        return body

    def generate_with_variant(self, customer: dict, instruction: str) -> str:
        """Apply one prevalidated experiment instruction to the normal draft."""
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(customer) + "\n\nExperiment writing instruction: " + instruction},
            ],
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
        )
        body = (response.choices[0].message.content or "").strip()
        if not body:
            raise ValueError("Groq returned an empty message")
        return body

    def recommend_action(self, contact: dict, context: dict | None = None) -> dict:
        """Choose one bounded action using supplied facts, never external tools."""
        facts = {
            "name": contact.get("name"),
            "company": contact.get("company"),
            "status": contact.get("status"),
            "interest_level": contact.get("interest_level"),
            "notes": contact.get("notes"),
            "next_followup": str(contact.get("next_followup") or ""),
            "context": context or {},
        }
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": "Recommend a sales follow-up action using only supplied facts. Return JSON with action (email, call_task, wait, or no_action) and a concise reason. Never invent an event or relationship."},
                {"role": "user", "content": json.dumps(facts, default=str)},
            ],
            max_tokens=180,
            temperature=0,
            response_format={"type": "json_object"},
        )
        decision = json.loads(response.choices[0].message.content or "{}")
        if decision.get("action") not in {"email", "call_task", "wait", "no_action"}:
            raise ValueError("Groq returned an unsupported action")
        return decision
