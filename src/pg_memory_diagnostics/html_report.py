from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from pg_memory_diagnostics.analysis import format_bytes
from pg_memory_diagnostics.models import Finding, ReportContext


def _severity_badge(severity: str) -> str:
    color = {
        "high": "#b42318",
        "medium": "#b54708",
        "low": "#175cd3",
    }.get(severity, "#344054")
    return f'<span class="badge" style="background:{color};">{escape(severity.upper())}</span>'


def _render_key_value_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
        for key, value in rows
    )
    return f"<table class=\"kv\">{body}</table>"


def _render_findings(findings: list[Finding], context: ReportContext) -> str:
    items: list[str] = []
    for finding in findings:
        suggested_queries = "".join(
            f"<li><strong>{escape(context.query_catalog[key].title)}</strong><br><code>{escape(key)}</code></li>"
            for key in finding.suggested_query_keys
            if key in context.query_catalog
        )
        evidence = "".join(f"<li>{escape(line)}</li>" for line in finding.evidence)
        items.append(
            "".join(
                [
                    '<section class="finding">',
                    f"<div class=\"finding-header\">{_severity_badge(finding.severity)}<h3>{escape(finding.title)}</h3></div>",
                    f"<p>{escape(finding.summary)}</p>",
                    f"<ul>{evidence}</ul>",
                    "<div class=\"follow-up\"><h4>Suggested follow-up queries</h4>",
                    f"<ul>{suggested_queries or '<li>No additional query suggestions for this finding.</li>'}</ul></div>",
                    "</section>",
                ]
            )
        )
    return "".join(items) or "<p>No findings were generated.</p>"


def _render_query_results(query_results: dict[str, list[dict[str, Any]]]) -> str:
    sections: list[str] = []
    for key, rows in query_results.items():
        sections.append(f"<section class=\"query-result\"><h3>{escape(key)}</h3>")
        if not rows:
            sections.append("<p>No rows returned.</p></section>")
            continue
        headers = list(rows[0].keys())
        thead = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
        body_rows = []
        for row in rows[:25]:
            body_rows.append(
                "<tr>"
                + "".join(f"<td>{escape(str(row.get(header, '')))}</td>" for header in headers)
                + "</tr>"
            )
        sections.append(f"<div class=\"table-wrap\"><table><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div></section>")
    return "".join(sections)


def _render_query_errors(query_errors: dict[str, str]) -> str:
    if not query_errors:
        return "<p>No query collection errors were recorded.</p>"
    items = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(error)}</td></tr>"
        for key, error in sorted(query_errors.items())
    )
    return f"<table class=\"kv\">{items}</table>"


def _render_query_catalog(context: ReportContext) -> str:
    keys = list(dict.fromkeys(context.derived.get("follow_up_query_keys", [])))
    blocks = []
    for key in keys:
        spec = context.query_catalog.get(key)
        if not spec:
            continue
        blocks.append(
            "".join(
                [
                    '<section class="sql-block">',
                    f"<h3>{escape(spec.title)}</h3>",
                    f"<p>{escape(spec.description)}</p>",
                    f"<pre><code>{escape(spec.sql)}</code></pre>",
                    "</section>",
                ]
            )
        )
    return "".join(blocks)


def render_report(context: ReportContext) -> str:
    metadata_rows = [
        ("Cloud profile", context.cloud.upper()),
        ("Collected at", str(context.metadata.get("collected_at", "unknown"))),
        ("Snapshot source", str(context.metadata.get("source", "unknown"))),
        ("Instance memory", format_bytes(context.derived.get("instance_memory_bytes", 0)) if context.derived.get("instance_memory_bytes") else "not supplied"),
    ]

    top_summary_rows = [
        ("shared_buffers", format_bytes(context.derived.get("shared_buffers_bytes", 0))),
        ("work_mem", format_bytes(context.derived.get("work_mem_bytes", 0))),
        ("maintenance_work_mem", format_bytes(context.derived.get("maintenance_work_mem_bytes", 0))),
        ("max_connections", str(context.derived.get("max_connections", 0))),
        ("current connections", str(context.derived.get("total_connections", 0))),
        ("idle connections", str(context.derived.get("idle_connections", 0))),
        ("temp bytes", format_bytes(context.derived.get("total_temp_bytes", 0))),
        ("worst-case connection memory", format_bytes(context.derived.get("worst_case_connection_mem_bytes", 0))),
        ("conservative total memory envelope", format_bytes(context.derived.get("potential_memory_commit_bytes", 0))),
    ]

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PostgreSQL Memory Diagnostics Report</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 0; background: #f8fafc; color: #101828; }}
    .page {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}
    .hero {{ background: linear-gradient(135deg, #0f172a, #1d4ed8); color: white; padding: 28px; border-radius: 20px; }}
    .hero h1 {{ margin: 0 0 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-top: 24px; }}
    .card, .finding, .sql-block, .query-result {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(16,24,40,.08); margin-top: 20px; }}
    .badge {{ display: inline-block; color: white; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 700; letter-spacing: .02em; }}
    .finding-header {{ display: flex; gap: 12px; align-items: center; }}
    .finding-header h3 {{ margin: 0; }}
    h2 {{ margin-top: 36px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e4e7ec; vertical-align: top; }}
    .kv th {{ width: 35%; color: #475467; }}
    .table-wrap {{ overflow-x: auto; }}
    pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 12px; overflow-x: auto; white-space: pre-wrap; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .muted {{ color: #475467; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>PostgreSQL Memory Diagnostics Report</h1>
      <p class="muted">Focused on memory configuration, spill indicators, and connection-driven risk for PostgreSQL on AWS, Google Cloud, and generic deployments.</p>
    </section>

    <div class="grid">
      <section class="card">
        <h2>Metadata</h2>
        {_render_key_value_table(metadata_rows)}
      </section>
      <section class="card">
        <h2>Top summary</h2>
        {_render_key_value_table(top_summary_rows)}
      </section>
    </div>

    <h2>Findings</h2>
    {_render_findings(context.findings, context)}

    <h2>Executed query results</h2>
    {_render_query_results(context.query_results)}

    <h2>Collection gaps and query errors</h2>
    <section class="card">
      {_render_query_errors(context.query_errors)}
    </section>

    <h2>Suggested diagnostic SQL</h2>
    {_render_query_catalog(context)}
  </div>
</body>
</html>
""".strip()


def write_report(context: ReportContext, output_path: str) -> None:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(context), encoding="utf-8")
