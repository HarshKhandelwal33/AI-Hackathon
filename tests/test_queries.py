from __future__ import annotations

import unittest
from datetime import datetime

from loglens.loader import event_template, parse_bgl, parse_openstack, read_raw_rows
from loglens.models import Filters
from loglens.queries import LogQueries


class FakeDatabase:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def fetch_all(self, query, parameters):
        self.calls.append((query, parameters))
        return self.rows


class QueryTests(unittest.TestCase):
    def test_search_is_bounded_and_auditable(self):
        database = FakeDatabase([{"event_id": str(i)} for i in range(4)])
        evidence = LogQueries(database, max_rows=10).search(
            Filters("bgl", severity="ERROR"), "cache failure", limit=3
        )
        self.assertEqual(3, evidence.result_count)
        self.assertTrue(evidence.truncated)
        self.assertIn("websearch_to_tsquery(%s)", evidence.query)
        self.assertEqual(["cache failure", "ERROR", 4], evidence.parameters)

    def test_rejects_reversed_time_window(self):
        with self.assertRaisesRegex(ValueError, "start must be earlier"):
            LogQueries(FakeDatabase()).trend(
                Filters(
                    "openstack",
                    start=datetime(2026, 1, 2),
                    end=datetime(2026, 1, 1),
                )
            )

    def test_group_by_is_allowlisted(self):
        database = FakeDatabase()
        evidence = LogQueries(database).summarize(Filters("openstack"), "team")
        self.assertIn("COALESCE(o.team, 'unmapped')", evidence.query)
        self.assertNotIn("team%", evidence.query)

    def test_text_filtered_summary_uses_full_index(self):
        database = FakeDatabase()
        evidence = LogQueries(database).summarize(
            Filters("bgl"), "component", text="cache failure"
        )
        self.assertIn("FROM bgl_logs_idx l", evidence.query)
        self.assertIn("l.message @@ websearch_to_tsquery(%s)", evidence.query)
        self.assertEqual(["cache failure", 21], evidence.parameters)

    def test_text_filtered_trend_uses_full_index(self):
        evidence = LogQueries(FakeDatabase()).trend(
            Filters("openstack"), "week", text="timeout"
        )
        self.assertIn("FROM openstack_logs_idx l", evidence.query)
        self.assertEqual(["timeout"], evidence.parameters)

    def test_parses_bgl_structured_row(self):
        parsed = parse_bgl({
            "LineId": "1", "Time": "2005-06-03-15.42.50.675872",
            "Component": "KERNEL", "Level": "INFO", "Node": "R02-M1",
            "EventTemplate": "cache parity error", "Content": "cache parity error corrected",
            "Label": "-",
        })
        self.assertEqual("bgl-1", parsed[0])
        self.assertEqual("KERNEL", parsed[3])
        self.assertIsNone(parsed[9])

    def test_parses_openstack_request_and_latency(self):
        parsed = parse_openstack({
            "LineId": "2", "Date": "2017-05-16", "Time": "00:00:00.272",
            "Logrecord": "nova-api.log.1", "Level": "INFO",
            "ADDR": "req-abc user-id tenant-id - - -",
            "EventTemplate": "request <*> time <*>105", "Content": "status: 200 time: 0.257",
        })
        self.assertEqual("nova-api", parsed[3])
        self.assertEqual("req-abc", parsed[6])
        self.assertEqual(257.0, parsed[10])
        self.assertEqual("tenant-id", parsed[11])

    def test_normalizes_dynamic_template_values(self):
        value = event_template("instance 3edec1e4-9678-4a3a-a21b-a145a4ee5e61 took 0.257")
        self.assertEqual("instance <UUID> took <NUM>", value)


if __name__ == "__main__":
    unittest.main()

