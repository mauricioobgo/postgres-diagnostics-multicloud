from __future__ import annotations

import json
from pathlib import Path
import unittest

from pg_memory_diagnostics.analysis import analyze_snapshot
from pg_memory_diagnostics.html_report import render_report


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_snapshot.json"


class HtmlReportTest(unittest.TestCase):
    def test_report_contains_expected_sections(self) -> None:
        snapshot = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        context = analyze_snapshot(snapshot=snapshot, cloud="aws", instance_memory_gib=16)
        report = render_report(context)

        self.assertIn("PostgreSQL Memory Diagnostics Report", report)
        self.assertIn("Suggested diagnostic SQL", report)
        self.assertIn("shared_buffers", report)
        self.assertIn("work_mem combined with connection count", report)
        self.assertIn("Collection gaps and query errors", report)
        self.assertIn("table_health", report)


if __name__ == "__main__":
    unittest.main()
