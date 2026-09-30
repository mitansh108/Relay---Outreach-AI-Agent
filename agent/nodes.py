import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.types import interrupt
from agent.state import FollowUpState
from agent.email_sender import send_email

# Generates Email For given customers and store every customer's draft email in Generated as a list
def make_generate_node(llm):
    """
    Factory — takes the FollowUpGenerator instance from session state
    and returns the generate node function.
    """
    def generate_followups(state: FollowUpState) -> dict:
        generated = []

        for customer in state["customers"]:
            try:
                body = llm.generate(
                    customer={
                        "name":             customer.get("name", ""),
                        "contact":          customer.get("contact", ""),
                        "company":          customer.get("company", ""),
                        "last_interaction": str(customer.get("last_interaction", "")),
                        "next_followup":    str(customer.get("next_followup", "")),
                        "status":           customer.get("status", ""),
                        "interest_level":   customer.get("interest_level", ""),
                        "notes":            customer.get("notes", ""),
                    },
                )
            except Exception as e:
                body = ""
                error = str(e)
            else:
                error = None

            generated.append({
                "name":     customer.get("name", ""),
                "email":    customer.get("contact", ""),
                "company":  customer.get("company", ""),
                "subject":  f"Following up — {customer.get('company', '')}",
                "body":     body,
                "approved": error is None,
                "error": error,
            }) # its per customer

        return {"generated_emails": generated}

    return generate_followups

# Interrupt Layer
def review_emails(state: FollowUpState) -> dict:
    """
    Pauses graph execution for human review.
    Streamlit will resume with edited emails via Command(resume=...).
    """
    reviewed = interrupt({"emails": state["generated_emails"]})#key^^
    return {"reviewed_emails": reviewed}

# Resume and SMTP layer to send email
def make_send_node(gmail_sender: str, gmail_password: str):
    def send_emails_node(state: FollowUpState) -> dict:
        results = []
        for email in state["reviewed_emails"]:
            if not email.get("approved", False) or email.get("error"):
                results.append({**email, "status": "skipped", "error": None})
                continue

            result = send_email(
                to=email["email"],
                subject=email["subject"],
                body=email["body"],
                sender=gmail_sender,
                app_password=gmail_password,
            )

            results.append({
                **email,
                "status": result["status"],
                "error":  result["error"],
            })

        return {"sent_results": results}
    return send_emails_node
