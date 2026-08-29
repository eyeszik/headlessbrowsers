"""
Governance checks for AI-generated content and media.

These are real, deterministic checks — not a statistical or Bayesian model.
Each check returns a plain pass/fail plus the specific reason, so failures
are debuggable and the logic is auditable by reading the code directly.

Four check categories, matching how the platform already talks about
compliance in CLAUDE.md and AssumptionLog:
  - legal:    PII / attribution concerns
  - ethical:  AI-disclosure requirement
  - security: prompt injection / XSS / SQL-injection-shaped input
  - resource: rate limit / cost guardrails
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GovernanceResult:
    """Outcome of one governance check category."""

    category: str
    passed: bool
    failed_checks: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


# ── Pattern libraries (kept as data so they're easy to extend/audit) ─────────

_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card_like": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |previous |prior )?instructions", re.IGNORECASE),
    re.compile(r"disregard (all |prior )?(instructions|rules)", re.IGNORECASE),
    re.compile(r"\bsystem\s*:", re.IGNORECASE),
    re.compile(r"\bassistant\s*:", re.IGNORECASE),
    re.compile(r"<\|im_start\|>"),
]

_XSS_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on(error|click|load|mouseover)\s*=", re.IGNORECASE),
    re.compile(r"<img[^>]+onerror", re.IGNORECASE),
]

_SQL_INJECTION_PATTERNS = [
    re.compile(r";\s*(drop|delete|truncate)\s+table", re.IGNORECASE),
    re.compile(r"\bunion\s+select\b", re.IGNORECASE),
    re.compile(r"'\s*or\s*'1'\s*=\s*'1", re.IGNORECASE),
]

_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
]


def check_legal(text_fields: Dict[str, str]) -> GovernanceResult:
    """
    Scan user-supplied text fields for PII that shouldn't be embedded in
    publicly-shared image metadata (title, description, keywords).
    """
    failed: List[str] = []
    matches: Dict[str, List[str]] = {}

    for field_name, text in text_fields.items():
        for pii_type, pattern in _PII_PATTERNS.items():
            found = pattern.findall(text or "")
            if found:
                failed.append(f"{field_name}:{pii_type}")
                matches.setdefault(field_name, []).append(pii_type)

    return GovernanceResult(
        category="legal",
        passed=len(failed) == 0,
        failed_checks=failed,
        details={"pii_matches": matches},
    )


def check_ethical(ai_disclosure_present: bool) -> GovernanceResult:
    """
    Verify the AI-generated disclosure requirement is set. This platform's
    convention (see CLAUDE.md) requires attributing AI-generated content —
    this check just enforces that a caller has actually set the flag rather
    than silently omitting it.
    """
    failed = [] if ai_disclosure_present else ["ai_disclosure_missing"]
    return GovernanceResult(
        category="ethical",
        passed=ai_disclosure_present,
        failed_checks=failed,
        details={"ai_disclosure_present": ai_disclosure_present},
    )


def check_security(text_fields: Dict[str, str]) -> GovernanceResult:
    """
    Scan for prompt injection, XSS, SQL-injection-shaped strings, and path
    traversal in any text destined for an LLM prompt, HTML display, or file
    path construction. This is defense-in-depth: the ORM already parameterizes
    queries and the API should already escape output — this check exists to
    catch and log clearly malicious input early, before it reaches those
    layers, and to reject it outright rather than silently sanitizing it.
    """
    failed: List[str] = []
    matched_text: Dict[str, str] = {}

    pattern_groups = {
        "prompt_injection": _PROMPT_INJECTION_PATTERNS,
        "xss": _XSS_PATTERNS,
        "sql_injection": _SQL_INJECTION_PATTERNS,
        "path_traversal": _PATH_TRAVERSAL_PATTERNS,
    }

    for field_name, text in text_fields.items():
        text = text or ""
        for group_name, patterns in pattern_groups.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    check_id = f"{field_name}:{group_name}"
                    failed.append(check_id)
                    matched_text[check_id] = match.group(0)[:50]

    return GovernanceResult(
        category="security",
        passed=len(failed) == 0,
        failed_checks=failed,
        details={"matched_patterns": matched_text},
    )


def check_resource(
    current_usage: int,
    limit: int,
    estimated_cost_usd: float,
    max_cost_usd: float,
) -> GovernanceResult:
    """
    Rate-limit and cost-budget guardrail. Uses the same request-counting
    concept as RateLimiter in services/integrations/base.py, but expressed
    as a stateless pre-check so callers can reject before doing any work.
    """
    failed: List[str] = []

    if current_usage >= limit:
        failed.append("rate_limit_exceeded")
    if estimated_cost_usd > max_cost_usd:
        failed.append("cost_budget_exceeded")

    return GovernanceResult(
        category="resource",
        passed=len(failed) == 0,
        failed_checks=failed,
        details={
            "current_usage": current_usage,
            "limit": limit,
            "estimated_cost_usd": estimated_cost_usd,
            "max_cost_usd": max_cost_usd,
        },
    )


def run_all_checks(
    text_fields: Dict[str, str],
    ai_disclosure_present: bool = True,
    current_usage: int = 0,
    rate_limit: int = 50,
    estimated_cost_usd: float = 0.0,
    max_cost_usd: float = 1.0,
) -> Dict[str, GovernanceResult]:
    """
    Run all four governance checks and return them keyed by category.
    Caller decides what to do on failure (reject, flag for review, etc.) —
    this function only reports, it doesn't enforce a policy.
    """
    return {
        "legal": check_legal(text_fields),
        "ethical": check_ethical(ai_disclosure_present),
        "security": check_security(text_fields),
        "resource": check_resource(
            current_usage, rate_limit, estimated_cost_usd, max_cost_usd
        ),
    }


def all_passed(results: Dict[str, GovernanceResult]) -> bool:
    return all(r.passed for r in results.values())


def collect_failures(results: Dict[str, GovernanceResult]) -> Dict[str, List[str]]:
    return {
        category: result.failed_checks
        for category, result in results.items()
        if not result.passed
    }
