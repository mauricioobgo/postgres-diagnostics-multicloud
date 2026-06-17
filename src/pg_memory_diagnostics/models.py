from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CloudType = str


@dataclass(slots=True)
class QuerySpec:
    key: str
    title: str
    sql: str
    description: str
    optional_extension: str | None = None


@dataclass(slots=True)
class Finding:
    id: str
    severity: str
    title: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    suggested_query_keys: list[str] = field(default_factory=list)
    # Plain-language fields so a non-expert reader understands the finding.
    category: str = "memory"  # memory | storage | connections | maintenance | config
    plain_explanation: str = ""
    recommendation: str = ""
    references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReportContext:
    cloud: CloudType
    metadata: dict[str, Any]
    settings: dict[str, dict[str, Any]]
    findings: list[Finding]
    query_results: dict[str, list[dict[str, Any]]]
    query_errors: dict[str, str]
    query_catalog: dict[str, QuerySpec]
    derived: dict[str, Any]
