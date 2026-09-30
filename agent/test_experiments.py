import unittest
from datetime import date

from agent.copilot import recommend
from agent.experiments import assign_variant, summarize_experiment, validate_experiment


TEST = {
    "id": "cta-sep-2026",
    "variable": "cta",
    "variants": [
        {"id": "control", "value": "soft", "weight": 70},
        {"id": "challenger", "value": "direct", "weight": 30},
    ],
    "start_date": "2026-09-01",
    "end_date": "2026-09-30",
    "min_per_variant": 100,
}


class ExperimentTests(unittest.TestCase):
    def test_stable_weighted_assignment(self):
        first = assign_variant("contact-42", TEST)
        self.assertEqual(first, assign_variant("contact-42", TEST))
        assigned = [assign_variant(f"contact-{i}", TEST)["variant_id"] for i in range(2000)]
        self.assertGreater(assigned.count("control"), 1300)
        self.assertLess(assigned.count("control"), 1500)

    def test_one_variable_and_duration_validation(self):
        validate_experiment(TEST)
        with self.assertRaises(ValueError):
            validate_experiment({**TEST, "variants": [{**TEST["variants"][0], "instruction": "change other things"}, TEST["variants"][1]]})
        with self.assertRaises(ValueError):
            validate_experiment({**TEST, "end_date": "2026-09-05"})

    def test_recommendation_carries_variant_and_changes_cta(self):
        contact = {"id": "abc", "name": "Asha", "contact": "asha@example.com", "company": "Acme", "notes": "Asked for a demo", "next_followup": "2026-09-20"}
        result = recommend(contact, experiment=TEST, now=date(2026, 9, 25))
        self.assertEqual(result["experiment"], assign_variant("abc", TEST))
        if result["experiment"]["value"] == "direct":
            self.assertIn("schedule a short call", result["draft"]["body"])
        else:
            self.assertIn("Happy to find a time", result["draft"]["body"])

    def test_no_winner_on_tiny_or_early_sample(self):
        tiny = [{"test_id": TEST["id"], "variant_id": "control", "contact_id": f"a{i}", "sent_at": "2026-09-15", "replied": True} for i in range(5)]
        early = summarize_experiment(TEST, tiny, now=date(2026, 9, 20))
        self.assertIsNone(early["winner"])
        late = summarize_experiment(TEST, tiny, now=date(2026, 10, 10))
        self.assertEqual(late["status"], "insufficient_data")

    def test_significant_result_after_all_gates(self):
        outcomes = []
        for variant, replies in (("control", 20), ("challenger", 50)):
            for i in range(120):
                outcomes.append({"test_id": TEST["id"], "variant_id": variant, "contact_id": f"{variant}-{i}", "sent_at": "2026-09-15", "replied": i < replies, "opted_out": False})
        result = summarize_experiment(TEST, outcomes, now=date(2026, 10, 10))
        self.assertEqual(result["status"], "winner")
        self.assertEqual(result["winner"], "challenger")
        outcomes[-1]["opted_out"] = True
        guarded = summarize_experiment(TEST, outcomes, now=date(2026, 10, 10))
        self.assertEqual(guarded["status"], "guardrail_review")
        self.assertIsNone(guarded["winner"])


if __name__ == "__main__":
    unittest.main()
