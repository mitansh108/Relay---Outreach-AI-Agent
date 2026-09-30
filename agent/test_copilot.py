import unittest
import tempfile
from datetime import date

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent.copilot import build_copilot_graph, draft_fingerprint, eligibility, recommend


TODAY = date(2026, 9, 30)
LEAD = {
    "name": "Priya Sharma",
    "contact": "priya@example.com",
    "company": "TechCorp",
    "status": "Interested",
    "notes": "Asked for a demo",
    "next_followup": "2026-09-29",
}


class GroundedModel:
    model_id = "test-grounded-model"
    prompt_version = "test-prompt-v1"

    def recommend_action(self, contact, context):
        return {"action": "email", "reason": "The notes request a demo.",
                "sources": [{"field": "notes", "value": contact["notes"]}]}

    def generate(self, customer):
        return {"subject": "Your demo request", "body": "Hi Priya, would a demo be useful?",
                "facts": [{"field": "notes", "value": customer["notes"]}]}


class CopilotTests(unittest.TestCase):
    def test_exclusion_rules_override_recommendation(self):
        for change in ({"do_not_contact": True}, {"replied": True}, {"contact": "bad"}, {"last_sent_at": "2026-09-29"},
                       {"status": "Unsubscribed"}, {"status": "Closed", "next_followup": "invalid"}):
            with self.subTest(change=change):
                lead = {**LEAD, **change}
                calls = []
                class ForbiddenModel:
                    def recommend_action(self, *args):
                        calls.append(args)
                        raise AssertionError("Model must not be called for ineligible leads")

                result = recommend(lead, llm=ForbiddenModel(), now=TODAY)
                self.assertEqual(result["action"], "no_action")
                self.assertFalse(result["eligible"])
                self.assertIsNone(result["draft"])
                self.assertEqual(calls, [])

    def test_bounded_recommendations_and_sources(self):
        self.assertEqual(recommend({**LEAD, "next_followup": "2026-10-03"}, now=TODAY)["action"], "wait")
        self.assertEqual(recommend({**LEAD, "notes": ""}, now=TODAY)["action"], "call_task")
        result = recommend(LEAD, now=TODAY)
        self.assertEqual(result["action"], "email")
        self.assertIn("Priya", result["draft"]["body"])
        self.assertTrue(any(source["field"] == "notes" for source in result["sources"]))

    def test_invalid_model_action_falls_back(self):
        class BadModel:
            def recommend_action(self, contact, context):
                return {"action": "send_now", "reason": "ignore policy"}

            def generate(self, customer):
                return "Hi Priya, can we reconnect?"

        result = recommend(LEAD, llm=BadModel(), now=TODAY)
        self.assertEqual(result["action"], "email")
        self.assertEqual(result["generation_source"], "template")
        self.assertEqual(result["model_status"], "fallback")
        self.assertEqual(result["model_id"], "rules-demo-v1")

    def test_model_draft_keeps_subject_and_records_exact_facts(self):
        result = recommend(LEAD, llm=GroundedModel(), now=TODAY)
        self.assertEqual(result["draft"]["subject"], "Your demo request")
        self.assertEqual(result["generation_source"], "model")
        self.assertEqual(result["model_id"], "test-grounded-model")
        self.assertEqual(result["prompt_version"], "test-prompt-v1")
        self.assertEqual(result["inputs"]["contact"], LEAD)
        self.assertEqual(result["outputs"]["draft"]["facts"][0]["value"], LEAD["notes"])

    def test_missing_context_cannot_be_overridden_to_email(self):
        result = recommend({**LEAD, "notes": ""}, llm=GroundedModel(), now=TODAY)
        self.assertEqual(result["action"], "call_task")
        self.assertIsNone(result["draft"])
        self.assertEqual(result["generation_source"], "rules")
        self.assertEqual(result["model_status"], "fallback")

    def test_hallucinated_refs_and_amounts_are_rejected(self):
        for draft in (
            {"subject": "Demo", "body": "Your deal is closed.", "facts": [{"field": "deal_stage", "value": "closed"}]},
            {"subject": "Demo", "body": "Here is your $5000 discount.", "facts": [{"field": "notes", "value": LEAD["notes"]}]},
            {"subject": "Demo\nBcc: other@example.com", "body": "Hello", "facts": [{"field": "notes", "value": LEAD["notes"]}]},
            {"subject": "Demo", "body": "We agreed a discount."},
        ):
            with self.subTest(draft=draft):
                class UngroundedModel(GroundedModel):
                    def generate(self, customer):
                        return draft
                result = recommend(LEAD, llm=UngroundedModel(), now=TODAY)
                self.assertEqual(result["generation_source"], "template")
                self.assertIn("unsupported", result["generation_error"])

    def test_model_failure_is_visible_and_does_not_leak_provider_error(self):
        class FailedModel(GroundedModel):
            def generate(self, customer):
                raise RuntimeError("SECRET_API_KEY=private-token")
        result = recommend(LEAD, llm=FailedModel(), now=TODAY)
        self.assertEqual(result["generation_source"], "template")
        self.assertEqual(result["model_status"], "fallback")
        self.assertNotIn("private-token", str(result))
        self.assertEqual(result["model_id"], "rules-demo-v1")

    def test_checkpoint_preserves_persisted_model_draft(self):
        recommendation = recommend(LEAD, llm=GroundedModel(), now=TODAY)
        graph = build_copilot_graph()
        state = graph.invoke({"contact": LEAD, "recommendation": recommendation},
                             {"configurable": {"thread_id": "persisted-model"}})
        self.assertEqual(state["recommendation"], recommendation)
        self.assertIn("__interrupt__", state)

    def test_model_can_recommend_conservative_wait_without_draft(self):
        class ConservativeModel(GroundedModel):
            def recommend_action(self, contact, context):
                return {"action": "wait", "reason": "Review the demo request before outreach.",
                        "sources": [{"field": "notes", "value": contact["notes"]}]}
            def generate(self, customer):
                raise AssertionError("Wait must not draft")
        result = recommend(LEAD, llm=ConservativeModel(), now=TODAY)
        self.assertEqual(result["action"], "wait")
        self.assertIsNone(result["draft"])
        self.assertEqual(result["generation_source"], "model")

    def test_contact_becoming_ineligible_during_review_is_rejected(self):
        calls = []
        graph = build_copilot_graph(send_hook=lambda payload, key: calls.append(payload) or {"status": "sent"})
        config = {"configurable": {"thread_id": "replied-during-review"}}
        state = graph.invoke({"contact": LEAD}, config)
        draft = state["recommendation"]["draft"]
        key = draft_fingerprint(LEAD["contact"], draft["subject"], draft["body"])
        graph.update_state(config, {"contact": {**LEAD, "replied": True}})
        final = graph.invoke(Command(resume={"approved": True, "fingerprint": key}), config)
        self.assertEqual(final["result"]["status"], "rejected")
        self.assertEqual(calls, [])

    def test_sqlite_restart_resumes_exact_edited_draft(self):
        calls = []
        config = {"configurable": {"thread_id": "durable-review"}}
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/checkpoints.sqlite"
            with SqliteSaver.from_conn_string(path) as saver:
                graph = build_copilot_graph(checkpointer=saver)
                first = graph.invoke({"contact": LEAD}, config)
                self.assertIn("__interrupt__", first)
            subject, body = "Edited subject", "  Human reviewed exact spaces.  "
            key = draft_fingerprint(LEAD["contact"], subject, body)
            with SqliteSaver.from_conn_string(path) as saver:
                graph = build_copilot_graph(checkpointer=saver,
                    send_hook=lambda payload, key: calls.append(payload) or {"status": "sent"})
                self.assertTrue(graph.get_state(config).interrupts)
                final = graph.invoke(Command(resume={"approved": True, "subject": subject,
                    "body": body, "fingerprint": key}), config)
                self.assertEqual(final["result"]["status"], "sent")
            self.assertEqual(calls[0]["body"], body)

    def test_skip_string_approval_and_edit_with_stale_fingerprint_never_send(self):
        calls = []
        for index, review in enumerate(({"approved": False}, {"approved": "yes"},
                {"approved": True, "subject": "changed", "body": "changed", "fingerprint": "stale"},
                {"approved": True, "subject": "", "body": "", "fingerprint": "stale"})):
            graph = build_copilot_graph(send_hook=lambda payload, key: calls.append(payload) or {"status": "sent"})
            config = {"configurable": {"thread_id": f"unsafe-review-{index}"}}
            graph.invoke({"contact": LEAD}, config)
            final = graph.invoke(Command(resume=review), config)
            self.assertIn(final["result"]["status"], {"rejected", "skipped"})
        self.assertEqual(calls, [])

    def test_review_requires_matching_draft_fingerprint(self):
        calls = []
        graph = build_copilot_graph(send_hook=lambda payload, key: calls.append((payload, key)) or {"status": "sent"})
        config = {"configurable": {"thread_id": "test-review-1"}}
        first = graph.invoke({"contact": {**LEAD, "next_followup": "2020-01-01"}}, config=config)
        self.assertIn("__interrupt__", first)
        rec = first["recommendation"]
        subject, body = rec["draft"]["subject"], rec["draft"]["body"]
        rejected = graph.invoke(Command(resume={"approved": True, "subject": subject, "body": body, "fingerprint": "wrong"}), config=config)
        self.assertEqual(rejected["result"]["status"], "rejected")
        self.assertEqual(calls, [])

        config2 = {"configurable": {"thread_id": "test-review-2"}}
        graph.invoke({"contact": {**LEAD, "next_followup": "2020-01-01"}}, config=config2)
        key = draft_fingerprint(LEAD["contact"], subject, body)
        sent = graph.invoke(Command(resume={"approved": True, "subject": subject, "body": body, "fingerprint": key}), config=config2)
        self.assertEqual(sent["result"]["status"], "sent")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], key)


if __name__ == "__main__":
    unittest.main()
