from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from pg_memory_diagnostics.analysis import format_bytes
from pg_memory_diagnostics.knowledge import GLOSSARY
from pg_memory_diagnostics.models import Finding, ReportContext


SEVERITY_COLORS = {
    "high": "#b42318",
    "medium": "#b54708",
    "low": "#175cd3",
}

CATEGORY_LABELS = {
    "memory": "Memory",
    "storage": "Storage",
    "connections": "Connections",
    "maintenance": "Maintenance / MVCC",
    "config": "Configuration",
}


def _severity_badge(severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, "#344054")
    return f'<span class="badge" style="background:{color};">{escape(severity.upper())}</span>'


def _category_tag(category: str) -> str:
    label = CATEGORY_LABELS.get(category, category.title())
    return f'<span class="tag">{escape(label)}</span>'


def _render_key_value_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
        for key, value in rows
    )
    return f"<table class=\"kv\">{body}</table>"


def _health_verdict(counts: dict[str, int]) -> tuple[str, str, str]:
    """Return (label, color, sentence) describing overall health."""
    high = counts.get("high", 0)
    medium = counts.get("medium", 0)
    if high > 0:
        return (
            "Needs attention",
            "#b42318",
            f"{high} high-severity issue(s) were found that can affect stability or performance and should be reviewed soon.",
        )
    if medium > 0:
        return (
            "Some risks",
            "#b54708",
            f"No high-severity issues, but {medium} medium-severity item(s) are worth tuning.",
        )
    return (
        "Looks healthy",
        "#067647",
        "No high or medium-severity issues were detected in the collected signals.",
    )


def _render_executive_summary(context: ReportContext) -> str:
    counts = context.derived.get("severity_counts", {"high": 0, "medium": 0, "low": 0})
    label, color, sentence = _health_verdict(counts)

    cache_pct = context.derived.get("overall_cache_hit_pct")
    cache_display = f"{cache_pct:.2f}%" if isinstance(cache_pct, (int, float)) else "n/a"

    cards = [
        ("Overall", label, color),
        ("High", str(counts.get("high", 0)), SEVERITY_COLORS["high"]),
        ("Medium", str(counts.get("medium", 0)), SEVERITY_COLORS["medium"]),
        ("Low", str(counts.get("low", 0)), SEVERITY_COLORS["low"]),
    ]
    score_cards = "".join(
        f'<div class="score"><span class="score-num" style="color:{c};">{escape(v)}</span>'
        f'<span class="score-label">{escape(k)}</span></div>'
        for k, v, c in cards
    )

    quick_rows = [
        ("Databases on disk", format_bytes(context.derived.get("total_database_bytes", 0))),
        ("Cache hit ratio", cache_display),
        ("Current connections", str(context.derived.get("total_connections", 0))),
        ("Temp file usage", format_bytes(context.derived.get("total_temp_bytes", 0))),
    ]

    return f"""
    <section class="card" id="summary">
      <h2>Executive summary</h2>
      <p class="lead" style="border-left:4px solid {color};">{escape(sentence)}</p>
      <div class="scores">{score_cards}</div>
      {_render_key_value_table(quick_rows)}
      <p class="muted small">Severity reflects potential impact, not certainty. "High" items deserve a closer look; "Low" items are mostly hygiene and informational notes.</p>
    </section>
    """


def _render_finding(finding: Finding, context: ReportContext) -> str:
    suggested_queries = "".join(
        f"<li><strong>{escape(context.query_catalog[key].title)}</strong> <code>{escape(key)}</code></li>"
        for key in finding.suggested_query_keys
        if key in context.query_catalog
    )
    evidence = "".join(f"<li>{escape(line)}</li>" for line in finding.evidence)
    references = "".join(
        f"<li>{_linkify(ref)}</li>" for ref in finding.references
    )

    explanation_block = (
        f'<div class="explain"><h4>What this means</h4><p>{escape(finding.plain_explanation)}</p></div>'
        if finding.plain_explanation
        else ""
    )
    recommendation_block = (
        f'<div class="fix"><h4>What to do</h4><p>{escape(finding.recommendation)}</p></div>'
        if finding.recommendation
        else ""
    )
    references_block = (
        f'<div class="refs"><h4>References</h4><ul>{references}</ul></div>'
        if references
        else ""
    )

    return "".join(
        [
            f'<section class="finding sev-{escape(finding.severity)}">',
            '<div class="finding-header">',
            _severity_badge(finding.severity),
            _category_tag(finding.category),
            f"<h3>{escape(finding.title)}</h3>",
            "</div>",
            f"<p>{escape(finding.summary)}</p>",
            explanation_block,
            recommendation_block,
            f'<div class="evidence"><h4>Evidence</h4><ul>{evidence}</ul></div>',
            '<div class="follow-up"><h4>Suggested follow-up queries</h4>',
            f"<ul>{suggested_queries or '<li>No additional query suggestions for this finding.</li>'}</ul></div>",
            references_block,
            "</section>",
        ]
    )


def _render_findings(findings: list[Finding], context: ReportContext) -> str:
    if not findings:
        return '<section class="card"><p>No findings were generated. The collected signals look healthy.</p></section>'
    return "".join(_render_finding(finding, context) for finding in findings)


def _linkify(text: str) -> str:
    """Turn a trailing URL in a reference string into a clickable link."""
    if "http://" in text or "https://" in text:
        idx = text.find("http")
        label = text[:idx].rstrip(" -—:")
        url = text[idx:].strip()
        safe_url = escape(url, quote=True)
        return f'{escape(label)} <a href="{safe_url}">{escape(url)}</a>'
    return escape(text)


def _render_bar(label: str, value_bytes: int, max_bytes: int) -> str:
    pct = (value_bytes / max_bytes * 100) if max_bytes else 0
    pct = max(0.5, min(100.0, pct))
    return (
        '<div class="bar-row">'
        f'<span class="bar-label">{escape(label)}</span>'
        f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.1f}%;"></span></span>'
        f'<span class="bar-value">{escape(format_bytes(value_bytes))}</span>'
        "</div>"
    )


def _render_storage_overview(context: ReportContext) -> str:
    db_rows = context.query_results.get("database_sizes") or []
    rel_rows = context.query_results.get("largest_relations") or []
    cache_rows = context.query_results.get("cache_hit_ratio") or []

    blocks: list[str] = []

    if db_rows:
        max_db = max((_to_int(r.get("size_bytes")) for r in db_rows), default=0)
        bars = "".join(
            _render_bar(str(r.get("database_name")), _to_int(r.get("size_bytes")), max_db)
            for r in db_rows[:8]
        )
        blocks.append(f"<h3>Database sizes</h3><div class=\"bars\">{bars}</div>")

    if rel_rows:
        max_rel = max((_to_int(r.get("total_bytes")) for r in rel_rows), default=0)
        bars = "".join(
            _render_bar(
                f"{r.get('schema_name')}.{r.get('relation_name')}",
                _to_int(r.get("total_bytes")),
                max_rel,
            )
            for r in rel_rows[:10]
        )
        blocks.append(f"<h3>Largest relations (table + indexes + TOAST)</h3><div class=\"bars\">{bars}</div>")

    if cache_rows:
        busy = [
            r for r in cache_rows
            if r.get("cache_hit_pct") is not None
            and (_to_int(r.get("blks_hit")) + _to_int(r.get("blks_read"))) > 0
        ]
        if busy:
            rows = "".join(
                f"<tr><td>{escape(str(r.get('database_name')))}</td>"
                f"<td>{escape(str(r.get('cache_hit_pct')))}%</td>"
                f"<td>{escape(format_bytes(_to_int(r.get('temp_bytes'))))}</td></tr>"
                for r in busy[:8]
            )
            blocks.append(
                "<h3>Cache hit ratio</h3>"
                '<div class="table-wrap"><table><thead><tr>'
                "<th>Database</th><th>Cache hit %</th><th>Temp written</th>"
                f"</tr></thead><tbody>{rows}</tbody></table></div>"
            )

    if not blocks:
        return ""
    return f'<section class="card" id="storage"><h2>Storage &amp; memory at a glance</h2>{"".join(blocks)}</section>'


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _render_query_results(query_results: dict[str, list[dict[str, Any]]], context: ReportContext) -> str:
    sections: list[str] = []
    for key, rows in query_results.items():
        spec = context.query_catalog.get(key)
        title = spec.title if spec else key
        sections.append(f'<section class="query-result"><h3>{escape(title)} <code>{escape(key)}</code></h3>')
        if spec:
            sections.append(f'<p class="muted small">{escape(spec.description)}</p>')
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
        sections.append(
            f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead>'
            f"<tbody>{''.join(body_rows)}</tbody></table></div></section>"
        )
    return "".join(sections)


def _render_query_errors(query_errors: dict[str, str]) -> str:
    if not query_errors:
        return "<p>No query collection errors were recorded.</p>"
    items = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(error)}</td></tr>"
        for key, error in sorted(query_errors.items())
    )
    return (
        '<p class="muted small">On managed services, a failed query is usually a permission limit or a hidden system view, not a database problem.</p>'
        f'<table class="kv">{items}</table>'
    )


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


def _render_glossary() -> str:
    rows = "".join(
        f"<tr><th>{escape(term)}</th><td>{escape(definition)}</td></tr>"
        for term, definition in GLOSSARY
    )
    return f'<section class="card" id="glossary"><h2>Glossary</h2><table class="kv">{rows}</table></section>'


def render_report(context: ReportContext) -> str:
    metadata_rows = [
        ("Cloud profile", context.cloud.upper()),
        ("Collected at", str(context.metadata.get("collected_at", "unknown"))),
        ("Snapshot source", str(context.metadata.get("source", "unknown"))),
        (
            "Instance memory",
            format_bytes(context.derived.get("instance_memory_bytes", 0))
            if context.derived.get("instance_memory_bytes")
            else "not supplied",
        ),
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
  <title>PostgreSQL Diagnostics Report</title>
  <style>
    :root {{ --ink:#101828; --muted:#475467; --line:#e4e7ec; --bg:#f8fafc; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Inter, -apple-system, Segoe UI, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--ink); line-height: 1.5; }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px; }}
    .hero {{ background: linear-gradient(135deg, #0f172a, #1d4ed8); color: white; padding: 28px; border-radius: 20px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .hero p {{ margin: 0; color: #cbd5e1; }}
    nav.toc {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }}
    nav.toc a {{ background: white; border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; text-decoration: none; color: #1d4ed8; font-size: 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
    .card, .finding, .sql-block, .query-result {{ background: white; border-radius: 16px; padding: 22px; box-shadow: 0 1px 3px rgba(16,24,40,.08); margin-top: 20px; }}
    .badge {{ display: inline-block; color: white; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 700; letter-spacing: .02em; }}
    .tag {{ display: inline-block; background:#eef2ff; color:#3730a3; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 600; }}
    .finding {{ border-left: 6px solid #344054; }}
    .finding.sev-high {{ border-left-color: {SEVERITY_COLORS['high']}; }}
    .finding.sev-medium {{ border-left-color: {SEVERITY_COLORS['medium']}; }}
    .finding.sev-low {{ border-left-color: {SEVERITY_COLORS['low']}; }}
    .finding-header {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .finding-header h3 {{ margin: 0; flex: 1 1 auto; }}
    .finding h4 {{ margin: 16px 0 6px; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }}
    .explain {{ background:#f0f9ff; border-radius:10px; padding:12px 16px; }}
    .fix {{ background:#ecfdf3; border-radius:10px; padding:12px 16px; margin-top:10px; }}
    .lead {{ font-size: 16px; padding-left: 14px; }}
    .scores {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }}
    .score {{ display: flex; flex-direction: column; align-items: center; min-width: 90px; background:#f9fafb; border:1px solid var(--line); border-radius: 12px; padding: 12px 16px; }}
    .score-num {{ font-size: 22px; font-weight: 800; }}
    .score-label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing:.04em; }}
    h2 {{ margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    .kv th {{ width: 38%; color: var(--muted); font-weight: 600; }}
    .table-wrap {{ overflow-x: auto; }}
    .bars {{ display: flex; flex-direction: column; gap: 8px; margin: 8px 0 4px; }}
    .bar-row {{ display: grid; grid-template-columns: 220px 1fr 110px; gap: 10px; align-items: center; font-size: 13px; }}
    .bar-label {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink); }}
    .bar-track {{ background:#eef2f6; border-radius: 999px; height: 14px; overflow: hidden; }}
    .bar-fill {{ display:block; height: 100%; background: linear-gradient(90deg,#3b82f6,#1d4ed8); }}
    .bar-value {{ text-align: right; color: var(--muted); }}
    pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 12px; overflow-x: auto; white-space: pre-wrap; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .finding code, .query-result h3 code {{ background:#f2f4f7; color:#344054; padding:1px 6px; border-radius:6px; }}
    .muted {{ color: var(--muted); }}
    .small {{ font-size: 13px; }}
    a {{ color: #1d4ed8; }}
    @media print {{
      body {{ background: white; }}
      .card, .finding, .sql-block, .query-result {{ box-shadow: none; border: 1px solid var(--line); }}
      nav.toc {{ display: none; }}
      pre {{ white-space: pre-wrap; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>PostgreSQL Diagnostics Report</h1>
      <p>Memory, storage, MVCC health, and connection risk for PostgreSQL on AWS RDS/Aurora, Google Cloud SQL, and generic deployments.</p>
    </section>

    <nav class="toc">
      <a href="#summary">Summary</a>
      <a href="#storage">Storage &amp; memory</a>
      <a href="#findings">Findings</a>
      <a href="#data">Collected data</a>
      <a href="#sql">Diagnostic SQL</a>
      <a href="#glossary">Glossary</a>
    </nav>

    {_render_executive_summary(context)}

    <div class="grid">
      <section class="card">
        <h2>Environment</h2>
        {_render_key_value_table(metadata_rows)}
      </section>
      <section class="card">
        <h2>Key memory settings</h2>
        {_render_key_value_table(top_summary_rows)}
      </section>
    </div>

    {_render_storage_overview(context)}

    <h2 id="findings">Findings</h2>
    {_render_findings(context.findings, context)}

    <h2 id="data">Collected data</h2>
    {_render_query_results(context.query_results, context)}

    <h2>Collection gaps and query errors</h2>
    <section class="card">
      {_render_query_errors(context.query_errors)}
    </section>

    <h2 id="sql">Suggested diagnostic SQL</h2>
    {_render_query_catalog(context)}

    {_render_glossary()}

    <p class="muted small" style="margin-top:24px;">Generated by pg-memory-diagnostics. Heuristics are intentionally conservative; confirm estimates (especially bloat) before making changes in production.</p>
  </div>
</body>
</html>
""".strip()


def write_report(context: ReportContext, output_path: str) -> None:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(context), encoding="utf-8")
