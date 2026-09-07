#!/usr/bin/env python3
"""Render a validated verifier-output.v1 JSON artifact as Markdown.

Usage:
  python3 render_report.py verifier-output.json
  python3 render_report.py verifier-output.json --out verifier-report.md
  python3 render_report.py verifier-output.json --safeguard-review /run/safeguard-review.json

The JSON artifact remains authoritative. This script validates it with the
bundled validator before writing a deterministic human-readable report.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


VERDICT_LABELS = {
    "reject": "Reject",
    "major_revision": "Major revision",
    "minor_revision": "Minor revision",
    "accept": "Accept",
}
CLASS_LABELS = {
    "central_unsalvageable_error": "Central unsalvageable error",
    "noncentral_unsalvageable_error": "Noncentral unsalvageable error",
    "major_repairable_gap": "Major repairable gap",
    "minor_repairable_gap": "Minor repairable gap",
    "cosmetic_or_exposition_only": "Cosmetic or exposition only",
}
SAFEGUARD_SCHEMA_VERSION = "ensemble-paper-audit.safeguard-review.v1"


def text(value: object) -> str:
    """Preserve mathematical notation while neutralizing raw HTML."""
    return html.escape(str(value), quote=False).replace("\r\n", "\n").strip()


def advisory_text(value: object) -> str:
    """Render reviewer/transcript text literally, without Markdown structure."""
    single_line = " ".join(text(value).split())
    return re.sub(r"([\\`*_{}\[\]()#+!|~$])", r"\\\1", single_line)


def validate_safeguard_review(review: Any) -> None:
    """Check the sidecar's display contract, allowing extra metadata."""
    if not isinstance(review, dict):
        raise ValueError("the review must be a JSON object")
    if review.get("schema_version") != SAFEGUARD_SCHEMA_VERSION:
        raise ValueError("unsupported or missing safeguard-review schema_version")
    if review.get("status") not in ("reviewed", "unavailable"):
        raise ValueError("status must be reviewed or unavailable")
    for key in ("provider", "model", "run_directory", "summary"):
        if not isinstance(review.get(key), str):
            raise ValueError(f"{key} must be a string")
    fingerprint = review.get("input_sha256")
    unavailable_before_packet = review["status"] == "unavailable" and fingerprint == ""
    if not unavailable_before_packet and (
        not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint)
    ):
        raise ValueError("input_sha256 must be a SHA-256 digest")
    limitations = review.get("limitations")
    if not isinstance(limitations, list) or any(
        not isinstance(item, str) for item in limitations
    ):
        raise ValueError("limitations must be an array of strings")
    concerns = review.get("concerns")
    if not isinstance(concerns, list):
        raise ValueError("concerns must be an array")
    for concern in concerns:
        if not isinstance(concern, dict) or any(
            not isinstance(concern.get(key), str)
            for key in ("category", "summary", "reason")
        ):
            raise ValueError("each concern needs category, summary, and reason strings")
        evidence = concern.get("evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(item, dict)
            or any(
                not isinstance(item.get(key), str)
                for key in ("artifact", "location", "excerpt")
            )
            for item in evidence
        ):
            raise ValueError("each concern needs an evidence array of artifact/location/excerpt strings")


def render_safeguard_reviews(paths: list[Path]) -> str:
    """Append advisory process reviews; never change mathematical outcomes."""
    lines = [
        "",
        "## Advisory safeguard review",
        "",
        "These model reviews concern search behavior, source relationships, and "
        "possible contamination. They are not mathematical findings, do not change "
        "the verdict or severity ranking, and do not automatically invalidate a run.",
        "",
    ]
    if not paths:
        lines.extend([
            "**Review unavailable.** No safeguard-review sidecar was supplied or "
            "found beside the mathematical output. This is not a clean review.",
            "",
        ])
        return "\n".join(lines)
    lines.extend([
        "**Coverage and provenance limitation:** Only the reviews listed below "
        "are included. This renderer does not establish that every contributing "
        "pass was reviewed, verify the reviews' recorded input fingerprints, or "
        "bind them to the mathematical report. Compare the source run records "
        "and preserved activity before relying on these assessments.",
        "",
    ])
    unavailable = 0
    for index, path in enumerate(paths, 1):
        lines.extend([
            f"### Process review {index}",
            "",
            f"**Review artifact:** {advisory_text(path)}",
            "",
        ])
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
            validate_safeguard_review(review)
        except (OSError, UnicodeError, ValueError) as exc:
            unavailable += 1
            detail = f"Could not read a usable safeguard review: {exc}"
            print(f"warning: {path}: {detail}", file=sys.stderr)
            lines.extend([
                "**Review unavailable.** The review artifact is missing or malformed. "
                "Its absence must not be interpreted as no suspicious activity.",
                "",
                f"**Limitation:** {advisory_text(detail)}",
                "",
            ])
            continue
        if review["status"] == "unavailable":
            unavailable += 1
            lines.extend([
                "**Review unavailable.** The safeguard assessment did not complete; "
                "this is not a clean review.",
                "",
            ])
        else:
            lines.extend(["**Status:** Reviewed (advisory only).", ""])
        if review.get("execution_mode") == "native" or review.get("reviewer_execution_mode") == "native":
            identities = review.get("reviewer_ids")
            identity_text = (", ".join(identities) if isinstance(identities, list) and identities
                             and all(isinstance(value, str) for value in identities)
                             else review.get("reviewer_id") or "Unavailable")
            lines.extend([
                "**Execution mode:** App-native subagents; no provider CLI subprocess was used for this review.",
                "",
                "**Native execution limitation:** Worker/reviewer isolation, tool restrictions, and "
                "complete activity capture are not established by CLI process controls. Any supplied "
                "activity export or worker ledger has recorded, not independently authenticated, "
                "provenance. Missing activity is not evidence that no unrecorded activity occurred.",
                "",
                f"**Recorded native reviewer ID(s):** {advisory_text(identity_text)}",
                "",
            ])
        if "planned_parts" in review:
            lines.extend([
                f"**Review packets completed:** {advisory_text(review.get('reviewed_parts', 0))} "
                f"of {advisory_text(review['planned_parts'])} planned.", "",
            ])
        if review.get("record_directory"):
            lines.extend([
                "**Preserved input and reviewer records (relative to the run):** "
                f"{advisory_text(review['record_directory'])}", "",
            ])
        lines.extend([
            f"**Run:** {advisory_text(review['run_directory'])}",
            "",
            f"**Reviewer:** {advisory_text(review['provider'])} / "
            f"{advisory_text(review['model'])}",
            "",
            "**Recorded input SHA-256 (not verified here):** "
            f"{review['input_sha256'] or 'Unavailable; no input fingerprint was recorded.'}",
            "",
            f"**Summary:** {advisory_text(review['summary'])}",
            "",
        ])
        artifacts = review.get("reviewed_artifacts")
        if isinstance(artifacts, list) and artifacts:
            lines.extend(["**Recorded input artifacts (hashes not verified here)**", ""])
            for artifact in artifacts:
                if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                    lines.append(
                        f"- {advisory_text(artifact['path'])}; "
                        f"SHA-256: {advisory_text(artifact.get('sha256', 'not recorded'))}"
                    )
                else:
                    lines.append("- Unusable artifact inventory entry; inspect the review JSON.")
            lines.append("")
        concerns = review["concerns"]
        if not concerns and review["status"] == "reviewed":
            lines.extend([
                "No suspicious activity was identified by this reviewer. This is "
                "not proof of compliance, independence, or mathematical correctness.",
                "",
            ])
        for concern in concerns:
            lines.extend([
                f"- **{advisory_text(concern['category'])}: "
                f"{advisory_text(concern['summary'])}**",
                f"  Reason: {advisory_text(concern['reason'])}",
            ])
            for evidence in concern["evidence"]:
                lines.append(
                    f"  - Evidence artifact: {advisory_text(evidence['artifact'])}; "
                    f"location: {advisory_text(evidence['location'])}; "
                    f"excerpt: {advisory_text(evidence['excerpt'])}"
                )
            if not concern["evidence"]:
                lines.append("  - No evidence pointer was supplied; inspect the source activity.")
            lines.append("")
        lines.extend(["**Reviewer limitations**", ""])
        if review["limitations"]:
            lines.extend(f"- {advisory_text(item)}" for item in review["limitations"])
        else:
            lines.append("No additional limitations were reported; this does not establish complete coverage.")
        lines.append("")
    if unavailable:
        lines.extend([
            f"**Incomplete safeguard coverage:** {unavailable} of {len(paths)} "
            "listed reviews were unavailable or unusable. The mathematical report "
            "above remains available, but those runs have no completed safeguard assessment.",
            "",
        ])
    return "\n".join(lines)


def render_native_provenance(path: Path) -> str:
    """Disclose a native run's limits even when no safeguard was prepared."""
    if not path.exists():
        return ""
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return (
            "\n## Execution provenance\n\n"
            "Run metadata could not be read; the execution mode and isolation evidence are unavailable.\n"
        )
    if not isinstance(metadata, dict) or metadata.get("execution_mode") != "native":
        return ""
    lines = [
        "", "## Execution provenance", "",
        f"**Recorded execution mode:** App-native ({advisory_text(metadata.get('provider', 'provider not recorded'))}).",
        "",
        f"**Recorded worker ID:** {advisory_text(metadata.get('native_worker_id') or 'Unavailable')}",
        "",
        "These are operator-recorded details, not proof of independent execution. "
        "Worker isolation and tool restrictions depend on the host app and instructions, "
        "not the CLI runner's process controls. Complete activity capture is not established.",
        "",
    ]
    if metadata.get("native_transcript"):
        lines.extend([
            "An activity export was recorded; its authenticity and completeness are not independently verified.", "",
        ])
    else:
        lines.extend([
            "No native activity export was recorded. Actual tool activity is unobserved, not confirmed clean.", "",
        ])
    limitations = metadata.get("audit_limitations", [])
    if isinstance(limitations, list):
        lines.extend(f"- {advisory_text(item)}" for item in limitations if isinstance(item, str))
        lines.append("")
    return "\n".join(lines)


def label(value: str) -> str:
    return value.replace("_", " ")


def location_text(location: dict[str, Any]) -> str:
    parts: list[str] = []
    if "section" in location:
        parts.append(text(location["section"]))
    if "theorem" in location:
        parts.append(text(location["theorem"]))
    if "statement" in location and location["statement"] != location.get("theorem"):
        parts.append(text(location["statement"]))
    if "proof" in location:
        parts.append(text(location["proof"]))
    if "equation" in location:
        parts.append(f"equation {text(location['equation'])}")
    if "page" in location:
        parts.append(f"PDF page {location['page']}")
    if "page_label" in location:
        parts.append(f"page label {text(location['page_label'])}")
    if "quote" in location:
        parts.append(f'“{text(location["quote"])}”')
    return "; ".join(parts)


def source_location_text(location: dict[str, Any]) -> str:
    parts: list[str] = []
    if "source_file" in location:
        parts.append(advisory_text(location["source_file"]))
    if "source_label" in location:
        parts.append(f"TeX label {advisory_text(location['source_label'])}")
    if "line_start" in location:
        if location.get("line_end") not in (None, location["line_start"]):
            parts.append(f"lines {location['line_start']}–{location['line_end']}")
        else:
            parts.append(f"line {location['line_start']}")
    return "; ".join(parts)


def bullet_list(items: list[str], empty: str = "None reported.") -> list[str]:
    if not items:
        return [empty]
    return [f"- {text(item)}" for item in items]


def evidence_reference(reference: str) -> str:
    rendered = text(reference)
    if reference.startswith(("https://", "http://")) and not any(
        char.isspace() for char in reference
    ):
        return f"<{rendered}>"
    return rendered


def render_finding(finding: dict[str, Any]) -> list[str]:
    centrality = finding["centrality"]
    repairability = finding["repairability"]
    confidence = finding["confidence"]
    reader_location = location_text(finding["location"])
    source_location = source_location_text(finding["location"])
    lines = [
        f"### {text(finding['finding_id'])} · {CLASS_LABELS[finding['class']]}",
        "",
        f"**Location:** {reader_location or 'Paper-level location not supplied; see the source anchor below.'}",
    ]
    if source_location:
        lines.extend(["", f"**Source anchor:** {source_location}"])
    lines.extend([
        "",
        f"**Confidence:** {label(confidence['level']).capitalize()} — "
        f"{text(confidence['rationale'])}",
        "",
        "**Claim checked**",
        "",
        text(finding["claim_under_review"]),
        "",
        "**Finding**",
        "",
        text(finding["problem"]),
        "",
        f"**Importance:** {label(centrality['value']).capitalize()} — "
        f"{text(centrality['rationale'])}",
    ])
    if centrality["dependency_path"]:
        path = " → ".join(text(item) for item in centrality["dependency_path"])
        lines.extend(["", f"**Dependency path:** {path}"])
    lines.extend(
        [
            "",
            f"**Repairability:** {label(repairability['value']).capitalize()}, "
            f"{label(repairability['effort'])} effort — "
            f"{text(repairability['rationale'])}",
            "",
            "**Evidence**",
            "",
        ]
    )
    for item in finding["evidence"]:
        supports = item.get("supports", [])
        support_note = (
            f" Supports: {', '.join(label(value) for value in supports)}."
            if supports
            else ""
        )
        lines.append(
            f"- **{text(item['evidence_id'])} · "
            f"{label(item['kind']).capitalize()}.** {text(item['summary'])} "
            f"Reference: {evidence_reference(item['reference'])}.{support_note}"
        )

    lines.extend(["", "**Unresolved checks**", ""])
    lines.extend(bullet_list(finding["unresolved_checks"]))
    lines.extend(["", "**Suggested repair tasks**", ""])
    if not finding["repair_tasks"]:
        lines.append("None specified.")
    else:
        for task in finding["repair_tasks"]:
            refs = task.get("evidence_refs", [])
            refs_note = f" Evidence: {', '.join(text(ref) for ref in refs)}." if refs else ""
            lines.append(
                f"- **{text(task['repair_task_id'])} · "
                f"{label(task['status']).capitalize()}.** {text(task['statement'])} "
                f"Success criterion: {text(task['success_criteria'])}.{refs_note}"
            )
    return lines


def render_report(output: dict[str, Any], source_name: str, source_hash: str) -> str:
    findings = output["findings"]
    coverage = output["coverage_notes"]
    lines = [
        "<!-- Generated from verifier-output.json; edit the JSON and rerun the renderer. -->",
        "# Verification Report",
        "",
        "> This report contains candidate findings for human review. It does not "
        "certify that the manuscript is correct or incorrect.",
        "",
        "## Outcome",
        "",
        f"- **Recommended disposition:** {VERDICT_LABELS[output['verdict']]}",
        f"- **Candidate findings:** {len(findings)}",
        "",
        "## Summary",
        "",
        text(output["summary"]),
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("No candidate findings were reported.")
    else:
        for index, finding in enumerate(findings):
            if index:
                lines.extend(["", "---", ""])
            lines.extend(render_finding(finding))

    lines.extend(["", "## Coverage", "", "### Reviewed regions", ""])
    lines.extend(bullet_list(coverage["reviewed_regions"]))
    lines.extend(["", "### Unreviewed or difficult regions", ""])
    lines.extend(bullet_list(coverage["unreviewed_or_difficult_regions"]))
    lines.extend(["", "### External checks not performed", ""])
    lines.extend(bullet_list(coverage["external_checks_not_performed"]))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "An `accept` recommendation means that no reportable defect was found "
            "within the audited material and stated coverage limits. It is not a "
            "proof that the manuscript is correct. Every candidate finding should "
            "be checked by a qualified reader before being treated as an error.",
            "",
            "---",
            "",
            f"Source: `{text(source_name)}`  ",
            f"SHA-256: `{source_hash}`",
            "",
        ]
    )
    return "\n".join(lines)


def validate(source: Path) -> None:
    validator = Path(__file__).with_name("validate_output.py")
    completed = subprocess.run(
        [sys.executable, str(validator), str(source)],
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode:
        detail = (completed.stdout + completed.stderr).strip()
        raise SystemExit(f"refusing to render invalid verifier output:\n{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="validated verifier-output.json")
    parser.add_argument(
        "--out",
        type=Path,
        help="output path (default: verifier-report.md beside the input)",
    )
    parser.add_argument(
        "--safeguard-review",
        type=Path,
        action="append",
        help="advisory safeguard-review.json; repeat for each contributing pass "
        "(default: discover a sibling safeguard-review.json)",
    )
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"no such file: {source}")
    destination = (
        args.out.expanduser().resolve()
        if args.out
        else source.with_name("verifier-report.md")
    )
    if destination == source:
        raise SystemExit("the Markdown output path must differ from the JSON input path")

    validate(source)
    raw = source.read_bytes()
    output = json.loads(raw)
    report = render_report(output, source.name, hashlib.sha256(raw).hexdigest())
    report += render_native_provenance(source.with_name("run.json"))
    review_paths = args.safeguard_review
    if review_paths is None:
        sibling = source.with_name("safeguard-review.json")
        review_paths = [sibling] if sibling.exists() else []
    review_paths = list(dict.fromkeys(path.expanduser().resolve() for path in review_paths))
    if destination in review_paths:
        raise SystemExit("the Markdown output path must differ from the safeguard review paths")
    report += render_safeguard_reviews(review_paths)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
