from __future__ import annotations

import json
from pathlib import Path
import unittest

from pg_memory_diagnostics.analysis import analyze_snapshot


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_snapshot.json"


class AnalysisTest(unittest.TestCase):
    def test_analysis_generates_high_signal_findings(self) -> None:
        snapshot = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        context = analyze_snapshot(snapshot=snapshot, cloud="aws", instance_memory_gib=16)

        finding_ids = {finding.id for finding in context.findings}

        self.assertIn("max-connections-high", finding_ids)
        self.assertIn("work-mem-risk", finding_ids)
        self.assertIn("temp-spills", finding_ids)
        self.assertIn("table-dead-tuples", finding_ids)
        self.assertIn("mvcc-blocker-long-xact", finding_ids)
        self.assertGreater(context.derived["potential_memory_commit_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
