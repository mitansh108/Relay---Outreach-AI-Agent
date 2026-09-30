import unittest
from datetime import date

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


class CopilotTests(unittest.TestCase):
    def test_exclusion_rules_override_recommendation(self):
        for change in ({"do_not_contact": True}, {"replied": True}, {"contact": "bad"}, {"last_sent_at": "2026-09-29"}):
            with self.subTest(change=change):
                lead = {**LEAD, **change}
                result = recommend(lead, now=TODAY)
                self.assertEqual(result["action"], "no_action")
                self.assertFalse(result["eligible"])
                self.assertIsNone(result["draft"])

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
        self.assertEqual(result["draft"]["body"], "Hi Priya, can we reconnect?")

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
