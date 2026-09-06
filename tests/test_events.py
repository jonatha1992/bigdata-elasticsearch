"""Contract tests for the synthetic event generator (README criterion 1).

The generator must be reproducible: the same seed and count always produce the
same events, with stable event IDs so that re-loading a dataset cannot create
duplicates (this sets up criteria 3 and 4). Standard library only.
"""

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from events import EVENT_TYPES, EventGenerator, ERROR_SEVERITIES


class EventGeneratorTests(unittest.TestCase):
    def test_generates_requested_count(self):
        events = EventGenerator(seed=42).generate(count=250)
        self.assertEqual(len(events), 250)

    def test_deterministic_for_same_seed(self):
        first = EventGenerator(seed=7).generate(count=500)
        second = EventGenerator(seed=7).generate(count=500)
        self.assertEqual(first, second)

    def test_different_seed_changes_events(self):
        a = EventGenerator(seed=1).generate(count=100)
        b = EventGenerator(seed=2).generate(count=100)
        self.assertNotEqual(a, b)

    def test_event_ids_unique_within_a_run(self):
        events = EventGenerator(seed=42).generate(count=1000)
        ids = [event["event_id"] for event in events]
        self.assertEqual(len(ids), len(set(ids)))

    def test_event_ids_stable_across_runs(self):
        ids_first = [e["event_id"] for e in EventGenerator(seed=42).generate(300)]
        ids_second = [e["event_id"] for e in EventGenerator(seed=42).generate(300)]
        self.assertEqual(ids_first, ids_second)

    def test_only_known_event_types(self):
        events = EventGenerator(seed=42).generate(count=2000)
        for event in events:
            self.assertIn(event["event_type"], EVENT_TYPES)

    def test_all_event_types_appear_in_large_sample(self):
        events = EventGenerator(seed=42).generate(count=5000)
        present = {event["event_type"] for event in events}
        self.assertEqual(present, set(EVENT_TYPES))

    def test_common_schema_fields(self):
        for event in EventGenerator(seed=3).generate(count=400):
            self.assertTrue(event["event_id"].startswith("evt-"))
            self.assertTrue(event["user_id"].startswith("u-"))
            self.assertTrue(event["session_id"].startswith("s-"))
            self.assertIn("@timestamp", event)

    def test_timestamps_are_iso8601_and_non_decreasing(self):
        events = EventGenerator(seed=9).generate(count=1000)
        parsed = [datetime.fromisoformat(e["@timestamp"]) for e in events]
        for earlier, later in zip(parsed, parsed[1:]):
            self.assertLessEqual(earlier, later)

    def test_search_event_schema(self):
        events = _by_type(EventGenerator(seed=42).generate(3000), "search")
        self.assertTrue(events)
        for event in events:
            self.assertIsInstance(event["query"], str)
            self.assertGreaterEqual(event["results_count"], 0)

    def test_view_event_schema(self):
        events = _by_type(EventGenerator(seed=42).generate(3000), "view")
        self.assertTrue(events)
        for event in events:
            self.assertTrue(event["product_id"].startswith("p-"))
            self.assertIsInstance(event["product_name"], str)
            self.assertIsInstance(event["category"], str)
            self.assertGreater(event["unit_price"], 0)

    def test_purchase_amount_is_price_times_quantity(self):
        events = _by_type(EventGenerator(seed=42).generate(3000), "purchase")
        self.assertTrue(events)
        for event in events:
            self.assertGreaterEqual(event["quantity"], 1)
            self.assertGreater(event["unit_price"], 0)
            self.assertEqual(
                event["amount"], event["unit_price"] * event["quantity"]
            )

    def test_error_event_schema(self):
        events = _by_type(EventGenerator(seed=42).generate(3000), "error")
        self.assertTrue(events)
        for event in events:
            self.assertTrue(event["error_code"].startswith("E-"))
            self.assertIn(event["severity"], ERROR_SEVERITIES)
            self.assertIsInstance(event["message"], str)

    def test_events_are_json_serializable(self):
        events = EventGenerator(seed=5).generate(count=100)
        # Round-trips without raising and preserves content.
        self.assertEqual(json.loads(json.dumps(events)), events)


def _by_type(events, event_type):
    return [event for event in events if event["event_type"] == event_type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
