from __future__ import annotations

import json
from pathlib import Path
import unittest

from pg_memory_diagnostics.analysis import analyze_snapshot
from pg_memory_diagnostics.html_report import render_report


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_snapshot.json"


class HtmlReportTest(unittest.TestCase):
    def setUp(self) -> None:
        snapshot = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.context = analyze_snapshot(snapshot=snapshot, cloud="aws", instance_memory_gib=16)
        self.report = render_report(self.context)

    def test_report_contains_expected_sections(self) -> None:
        self.assertIn("PostgreSQL Diagnostics Report", self.report)
        self.assertIn("Executive summary", self.report)
        self.assertIn("Suggested diagnostic SQL", self.report)
        self.assertIn("shared_buffers", self.report)
        self.assertIn("work_mem combined with connection count", self.report)
        self.assertIn("Collection gaps and query errors", self.report)
        self.assertIn("table_health", self.report)

    def test_report_includes_storage_and_glossary(self) -> None:
        self.assertIn("Storage &amp; memory at a glance", self.report)
        self.assertIn("Largest relations", self.report)
        self.assertIn("Cache hit ratio", self.report)
        self.assertIn("Glossary", self.report)
        self.assertIn("MVCC", self.report)

    def test_report_includes_plain_language_guidance(self) -> None:
        self.assertIn("What this means", self.report)
        self.assertIn("What to do", self.report)


if __name__ == "__main__":
    unittest.main()
