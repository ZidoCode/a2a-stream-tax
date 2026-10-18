"""Tests for a2a-stream-tax — deterministic, no network."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import a2a_stream_tax as st


def ev(kind="status-update", state="working", artifact_id=None):
    res = {"kind": kind, "taskId": "t1", "contextId": "c1"}
    if kind == "status-update":
        res["status"] = {"state": state}
        res["final"] = False
    else:
        res["artifact"] = {"artifactId": artifact_id or "a1",
                           "parts": [{"kind": "text", "text": "x" * 40}]}
    return {"jsonrpc": "2.0", "id": 1, "result": res}


class TestLoadStream(unittest.TestCase):
    def test_parse_and_skip(self):
        p = "/tmp/st_test.jsonl"
        with open(p, "w") as f:
            f.write(json.dumps(ev()) + "\nnot json\n\n" + json.dumps(ev("artifact-update")) + "\n")
        events, bad = st.load_stream(p)
        self.assertEqual(len(events), 2)
        self.assertEqual(len(bad), 1)

    def test_non_object_lines_rejected(self):
        p = "/tmp/st_test2.jsonl"
        with open(p, "w") as f:
            f.write("[1,2]\n" + json.dumps(ev()) + "\n")
        events, bad = st.load_stream(p)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(bad), 1)


class TestClassify(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(st.classify(ev()), "status")
        self.assertEqual(st.classify(ev("artifact-update")), "artifact")
        self.assertEqual(st.classify({"jsonrpc": "2.0", "error": {}}), "error")
        self.assertEqual(st.classify({"jsonrpc": "2.0"}), "other")


class TestMeasure(unittest.TestCase):
    def test_totals_sum(self):
        events = [ev() for _ in range(3)] + [ev("artifact-update") for _ in range(2)]
        m = st.measure(events)
        self.assertEqual(m["events"], 5)
        manual = sum(st.event_tokens(e) for e in events)
        self.assertEqual(m["total"], manual)
        self.assertEqual(m["buckets"]["status"]["count"], 3)
        self.assertEqual(m["buckets"]["artifact"]["count"], 2)

    def test_envelope_non_negative(self):
        m = st.measure([ev(), ev("artifact-update")])
        self.assertGreaterEqual(m["envelope"], 0)


class TestSimulate(unittest.TestCase):
    def setUp(self):
        self.card = {"name": "x", "description": "y" * 40, "skills": []}

    def test_more_updates_more_cost(self):
        a = st.simulate(self.card, updates=5, artifacts=1)
        b = st.simulate(self.card, updates=50, artifacts=1)
        self.assertGreater(b["total"], a["total"])

    def test_breaks_down(self):
        m = st.simulate(self.card, updates=10, artifacts=2)
        expected = m["card_tokens"] + m["per_status_tokens"] * 10 + m["per_artifact_tokens"] * 2
        self.assertEqual(m["total"], expected)

    def test_zero_events_card_only(self):
        m = st.simulate(self.card, updates=0, artifacts=0)
        self.assertEqual(m["total"], m["card_tokens"])


class TestReport(unittest.TestCase):
    def test_report_shape(self):
        events = [ev() for _ in range(10)] + [ev("artifact-update") for _ in range(3)]
        out, m = st.report(events, 3.0)
        self.assertIn("TOTAL streamed", out)
        self.assertIn("savings", out)
        self.assertIn("%", out)

    def test_empty_stream(self):
        out, m = st.report([], 3.0)
        self.assertIn("empty", out)
        self.assertIsNone(m)

    def test_after_fix_never_negative(self):
        events = [ev() for _ in range(100)]
        out, m = st.report(events, 3.0)
        self.assertIn("after fix", out)


class TestEnvelopeAccounting(unittest.TestCase):
    def test_status_message_is_payload_not_envelope(self):
        # A status event carrying a long agent message is mostly content; the
        # old code booked the whole event as envelope overhead.
        ev_ = {"jsonrpc": "2.0", "id": 1, "result": {
            "kind": "status-update", "taskId": "t1",
            "status": {"state": "working", "message": {
                "role": "agent", "parts": [{"kind": "text", "text": "x" * 800}]}}}}
        m = st.measure([ev_])
        self.assertLess(m["envelope"], m["total"] * 0.5, m)

    def test_envelope_tracked_per_kind(self):
        ev_ = {"jsonrpc": "2.0", "id": 1, "result": {
            "kind": "artifact-update", "taskId": "t1",
            "artifact": {"artifactId": "a1", "parts": [{"kind": "data", "data": {}}]}}}
        m = st.measure([ev_])
        self.assertIn("envelope", m["buckets"][st.classify(ev_)])

    def test_simulate_reports_status_share(self):
        card = {"name": "x", "description": "y" * 40, "skills": []}
        m = st.simulate(card, updates=10, artifacts=2)
        self.assertIn("status_share_pct", m)
        self.assertNotIn("envelope_share_pct", m)


class TestEventTokens(unittest.TestCase):
    def test_deterministic(self):
        e = ev()
        self.assertEqual(st.event_tokens(e), st.event_tokens(e))
        self.assertGreater(st.event_tokens(e), 0)


if __name__ == "__main__":
    unittest.main()
