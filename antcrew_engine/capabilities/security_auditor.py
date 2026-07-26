"""SecurityAuditor — LLM-based cross-file security consistency audit.

Unlike SecurityScanner (which runs pip-audit for CVEs), this capability reads
the full source tree and applies two-phase LLM reasoning:

  Phase 1 — catalog every established defensive control (auth guards,
             CSRF, rate limits, input validation, encryption, …).
  Phase 2 — find code paths that do similar things but are MISSING the
             same controls, plus classic anti-patterns (SSRF, path
             traversal, hardcoded secrets, fail-open auth, …).

The cross-file consistency check — "pattern exists in A, absent in B" —
is the main differentiator over static linters like bandit, which reason
per-file.  An LLM with full-repo context can maintain the catalog and
check every equivalent surface against it.

Output: a REPORT artifact whose content is a dict with:
  {
    "findings": [ <AuditFinding dicts> ],
    "catalog":  [ <established control dicts> ],
    "summary":  "<free-text summary>",
  }

Each AuditFinding dict:
  {
    "severity":      "critical|high|medium|low|info",
    "pattern_class": "ssrf|idor|path_traversal|auth_bypass|xss|secret|
                      race_condition|csrf|injection|fail_open|consistency|…",
    "file_path":     "app/api/reviews.py",
    "line_number":   277,          # int or null
    "title":         "Short title",
    "evidence":      "Why it is exploitable…",
    "reference_fix": "Same guard in app/api/tickets.py:68 — apply the same pattern",
                     # null if no existing fix pattern in codebase
  }
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from antcrew_engine.engine import (
    Artifact,
    ArtifactDelta,
    ArtifactId,
    ArtifactKind,
    CapabilityDescriptor,
    CapabilityResult,
    ConditionId,
)

from ._utils import parse_json
from .base import BaseExecutor

# ---------------------------------------------------------------------------
# File filtering
# ---------------------------------------------------------------------------

_INCLUDE_EXTENSIONS = {".py", ".html", ".js", ".ts", ".yaml", ".yml", ".toml", ".env.example"}
_EXCLUDE_DIRS = {
    "alembic", "migrations", "__pycache__", ".git", "node_modules",
    "vendor", "dist", "build", ".venv", "venv", "env",
}
_EXCLUDE_FILENAME_PATTERNS = [
    re.compile(r"^\d{3}_.*\.py$"),   # Alembic version files like 001_initial_schema.py
    re.compile(r"^test_.*\.py$"),
    re.compile(r"^conftest\.py$"),
]
# Max total chars of source fed to the LLM (≈ 40 k tokens at 4 chars/token)
_MAX_SOURCE_CHARS = 160_000
# Max chars per individual file (large files are truncated)
_MAX_FILE_CHARS = 8_000


def _is_relevant(file_path: str) -> bool:
    p = Path(file_path)
    # Exclude by directory component
    for part in p.parts[:-1]:
        if part.lower() in _EXCLUDE_DIRS:
            return False
    # Exclude by extension
    if p.suffix.lower() not in _INCLUDE_EXTENSIONS:
        return False
    # Exclude by filename pattern
    for pat in _EXCLUDE_FILENAME_PATTERNS:
        if pat.match(p.name):
            return False
    return True


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PHASE1_SYSTEM = """\
You are a senior application security engineer auditing a Python web application.

TASK — Phase 1: catalog every defensive security control established in this codebase.

Look for any of the following (not exhaustive):
- Authentication guards (require_api_key, session checks, token validation)
- Authorization checks (workspace_id scoping, ownership validation, role checks)
- Input validation and sanitisation (URL allow-listing, path traversal prevention,
  HTML escaping, file extension checks)
- CSRF protection (token or double-submit cookie)
- Rate limiting
- Encryption at rest (BYOK, password hashing algorithms)
- Output encoding
- Secure cookie flags

For each control found output a JSON object:
{
  "control_type": "short snake_case name e.g. require_api_key",
  "file_path":    "relative/path/to/file.py",
  "location":     "function or route name, or line range",
  "description":  "one sentence — what attack does this prevent?"
}

Output ONLY a JSON object (no markdown fences, no prose):
{
  "controls": [ … ],
  "summary":  "One paragraph overview of the security posture of this codebase."
}"""

_PHASE2_SYSTEM = """\
You are a senior application security engineer performing a targeted security audit.

You will receive:
  1. A catalog of security controls already established in this codebase.
  2. The full application source code.

YOUR TASK — find real security findings:

A) CROSS-FILE CONSISTENCY — code paths that perform the same operation as a
   protected path but are MISSING the same control.
   Example: validate_external_url() is called before fetching repo_url, but a
   different endpoint also fetches an external URL without the same guard.
   These are the hardest for linters to find; your full-repo context is the key.

B) CLASSIC VULNERABILITIES — look for:
   - SQL injection (raw string interpolation into queries)
   - Path traversal (user input in file paths without sanitisation)
   - SSRF (outbound requests to user-supplied URLs without allow-listing)
   - Stored / reflected XSS (user input interpolated into HTML without escaping)
   - Hardcoded secrets, tokens, or passwords in source
   - Fail-open auth logic (if resource is None → access granted instead of denied)
   - Race conditions (TOCTOU patterns in critical flows)
   - IDOR (object accessed directly by user-supplied ID without workspace/owner check)
   - Insecure direct object references in API routes

RULES:
- Only report findings where you can articulate a concrete exploitation scenario.
- Do NOT report low-signal code smells ("this could be improved") — only exploitable issues.
- If no findings exist in a category, omit it entirely — do not pad the list.
- For each finding, if an equivalent fix pattern already exists elsewhere in the
  codebase, set reference_fix to the file + line + description so BugFixer can
  replicate it mechanically.

Output ONLY a JSON array (no markdown fences, no prose):
[
  {
    "severity":      "critical|high|medium|low|info",
    "pattern_class": "ssrf|idor|path_traversal|auth_bypass|xss|secret|race_condition|csrf|injection|fail_open|consistency",
    "file_path":     "app/api/reviews.py",
    "line_number":   277,
    "title":         "Concise title (< 80 chars)",
    "evidence":      "Concrete attack scenario — what an attacker can do and how.",
    "reference_fix": "Same guard in app/api/tickets.py:68 — apply the same pattern"
  }
]

If there are zero findings output an empty array: []"""


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

class SecurityAuditor(BaseExecutor):
    """LLM-based cross-file security consistency audit.

    Reads SOURCE artifacts in the store, runs a two-phase LLM audit (catalog
    established controls → find gaps), and returns a REPORT artifact with
    structured AuditFinding dicts.

    The platform controls which files land in the store (full vs. diff mode is
    handled at the file-fetch layer before calling the auditor).
    """

    descriptor = CapabilityDescriptor(
        name        = "security_auditor",
        description = (
            "LLM-based cross-file security audit: catalogs established controls then "
            "finds consistency gaps and classic vulnerabilities across the repo."
        ),
        needs       = frozenset([ConditionId("implementation_exists")]),
        produces    = frozenset([ConditionId("security_audit_done")]),
        emits       = frozenset(["report"]),
        cost        = 2.5,
    )

    def _run(self, store, goal) -> CapabilityResult:
        sources = store.list(ArtifactKind.SOURCE)
        scope_paths: set[str] | None = None  # reserved for future use via goal.constraints.custom

        # Build the source block fed to the LLM
        source_block, included = _build_source_block(sources, scope_paths)

        if not included:
            return CapabilityResult(
                errors=["No relevant source files found in the artifact store. "
                        "Ensure implementation_exists condition is satisfied."]
            )

        # ── Phase 1: build security-control catalog ──────────────────────────
        catalog_raw = self._call_json(
            _PHASE1_SYSTEM,
            f"Goal: {goal.description}\n\nSource files:\n{source_block}",
        )
        catalog_obj = _safe_parse_obj(catalog_raw)
        controls = catalog_obj.get("controls", [])
        catalog_summary = catalog_obj.get("summary", "")

        catalog_block = json.dumps({"controls": controls, "summary": catalog_summary}, indent=2)

        # ── Phase 2: find gaps and anti-patterns ─────────────────────────────
        phase2_user = (
            f"Goal: {goal.description}\n\n"
            f"Established security controls (catalog):\n{catalog_block}\n\n"
            f"Source files:\n{source_block}"
        )
        findings_raw = self._call_json(_PHASE2_SYSTEM, phase2_user)
        findings = _safe_parse_list(findings_raw)

        report_content = {
            "findings": findings,
            "catalog":  controls,
            "summary":  catalog_summary,
            "files_audited": included,
        }

        report_artifact = Artifact(
            id       = ArtifactId("security_audit_report"),
            kind     = ArtifactKind.REPORT,
            content  = report_content,
            metadata = {"file_path": ".antcrew/security_audit_report.json"},
        )
        return CapabilityResult(delta=ArtifactDelta(created=(report_artifact,)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_source_block(
    sources: list,
    scope_paths: set[str] | None,
) -> tuple[str, list[str]]:
    """Build the text block fed to the LLM and return (block, included_paths)."""
    # Prioritise by path depth (shallower = more core) then alphabetically
    relevant = [
        art for art in sources
        if isinstance(art.content, str)
        and _is_relevant(art.metadata.get("file_path", str(art.id)))
        and (scope_paths is None or art.metadata.get("file_path") in scope_paths)
    ]
    relevant.sort(key=lambda a: (
        len(Path(a.metadata.get("file_path", "")).parts),
        a.metadata.get("file_path", ""),
    ))

    parts: list[str] = []
    total_chars = 0
    included: list[str] = []

    for art in relevant:
        fp = art.metadata.get("file_path", str(art.id))
        content = art.content
        if len(content) > _MAX_FILE_CHARS:
            content = content[:_MAX_FILE_CHARS] + f"\n… [truncated at {_MAX_FILE_CHARS} chars]"
        entry = f"### {fp}\n{content}"
        if total_chars + len(entry) > _MAX_SOURCE_CHARS:
            break
        parts.append(entry)
        total_chars += len(entry)
        included.append(fp)

    return "\n\n".join(parts), included


def _safe_parse_obj(raw: str) -> dict:
    try:
        result = parse_json(raw)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _safe_parse_list(raw: str) -> list:
    try:
        result = parse_json(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return []
