#!/usr/bin/env python3
"""Validate external-obligation and external-verification artifacts.

Usage:
  python3 validate_external_artifacts.py EXTERNAL-OBLIGATIONS.json [--coverage-input COVERAGE.json]
  python3 validate_external_artifacts.py EXTERNAL-OBLIGATIONS.json EXTERNAL-VERIFICATION.json [--coverage-input COVERAGE.json]
  python3 validate_external_artifacts.py EXTERNAL-OBLIGATIONS.json EXTERNAL-VERIFICATION.json CITATION-FETCH-LOG.json [--coverage-input COVERAGE.json]
  python3 validate_external_artifacts.py EXTERNAL-OBLIGATIONS.json EXTERNAL-VERIFICATION.json CITATION-FETCH-LOG.json VERIFIER-OUTPUT.json [--coverage-input COVERAGE.json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


FETCH_LOG_FIELDS = {
    "kind",
    "obligation_id",
    "query",
    "url",
    "used",
    "relationship_to_manuscript",
    "reason",
}
COVERAGE_PROVENANCE = {
    "global": "global",
    "decomposed": "decomposed",
    "argument-spine": "argument_spine",
    "refuter": "refuter",
}


class SchemaChecker:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    def resolve(self, ref: str, current: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if ref.startswith("#"):
            document, fragment = current, ref[1:]
        else:
            base, _, fragment = ref.partition("#")
            document = self.documents[base]
        node: Any = document
        for part in fragment.lstrip("/").split("/") if fragment else []:
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node, document

    def errors(
        self,
        value: Any,
        schema: dict[str, Any],
        current: dict[str, Any],
        path: str = "<root>",
    ) -> list[str]:
        if "$ref" in schema:
            target, document = self.resolve(schema["$ref"], current)
            return self.errors(value, target, document, path)

        problems: list[str] = []
        if "const" in schema and value != schema["const"]:
            problems.append(f"{path}: expected {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            problems.append(f"{path}: {value!r} is not one of {schema['enum']!r}")

        expected = schema.get("type")

        def matches_type(name: str) -> bool:
            return {
                "object": isinstance(value, dict),
                "array": isinstance(value, list),
                "string": isinstance(value, str),
                "integer": isinstance(value, int) and not isinstance(value, bool),
                "number": isinstance(value, (int, float)) and not isinstance(value, bool),
                "boolean": isinstance(value, bool),
                "null": value is None,
            }.get(name, True)

        type_ok = (
            any(matches_type(name) for name in expected)
            if isinstance(expected, list)
            else matches_type(expected)
            if isinstance(expected, str)
            else True
        )
        if not type_ok:
            return problems + [f"{path}: expected {expected}"]

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                problems.append(f"{path}: string is too short")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                problems.append(f"{path}: string is too long")
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                problems.append(f"{path}: does not match {schema['pattern']!r}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                problems.append(f"{path}: must be at least {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                problems.append(f"{path}: must be at most {schema['maximum']}")

        if isinstance(value, dict):
            for key in schema.get("required", []):
                if key not in value:
                    problems.append(f"{path}: missing required property {key!r}")
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            for key in value.keys() - properties.keys():
                if additional is False:
                    problems.append(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    problems.extend(
                        self.errors(value[key], additional, current, f"{path}/{key}")
                    )
            for key, child_schema in properties.items():
                if key in value:
                    problems.extend(self.errors(value[key], child_schema, current, f"{path}/{key}"))

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                problems.append(f"{path}: array is too short")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                problems.append(f"{path}: array is too long")
            if schema.get("uniqueItems"):
                encoded = [json.dumps(item, sort_keys=True) for item in value]
                if len(encoded) != len(set(encoded)):
                    problems.append(f"{path}: array items are not unique")
            if "items" in schema:
                for index, item in enumerate(value):
                    problems.extend(self.errors(item, schema["items"], current, f"{path}/{index}"))
            if "contains" in schema:
                matches = sum(
                    not self.errors(item, schema["contains"], current, f"{path}/{index}")
                    for index, item in enumerate(value)
                )
                if matches < schema.get("minContains", 1):
                    problems.append(f"{path}: contains matched {matches} item(s)")

        for subschema in schema.get("allOf", []):
            problems.extend(self.errors(value, subschema, current, path))
        if "anyOf" in schema and not any(
            not self.errors(value, subschema, current, path)
            for subschema in schema["anyOf"]
        ):
            problems.append(f"{path}: no anyOf branch matched")
        if "oneOf" in schema:
            matches = sum(
                not self.errors(value, subschema, current, path)
                for subschema in schema["oneOf"]
            )
            if matches != 1:
                problems.append(f"{path}: oneOf matched {matches} branches")
        if "not" in schema and not self.errors(value, schema["not"], current, path):
            problems.append(f"{path}: forbidden schema matched")
        if "if" in schema and not self.errors(value, schema["if"], current, path):
            problems.extend(self.errors(value, schema.get("then", {}), current, path))
        return problems


def schema_dir() -> Path:
    bundle = Path(__file__).resolve().parent.parent
    for candidate in (bundle / "references" / "schema", bundle / "contract"):
        if (candidate / "external-obligations.schema.json").is_file():
            return candidate
    raise SystemExit("could not locate external artifact schemas")


def load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def report(problems: list[str]) -> int:
    if not problems:
        return 0
    print("external artifacts: INVALID")
    for problem in problems[:30]:
        print(f"  - {problem}")
    if len(problems) > 30:
        print(f"  - ... and {len(problems) - 30} more")
    return 1


def parse_arguments(argv: list[str]) -> tuple[list[Path], Path | None]:
    arguments = list(argv)
    coverage_path: Path | None = None
    if "--coverage-input" in arguments:
        if arguments.count("--coverage-input") != 1:
            raise SystemExit("--coverage-input may be supplied only once")
        index = arguments.index("--coverage-input")
        if index + 1 >= len(arguments):
            raise SystemExit("--coverage-input requires a path")
        coverage_path = Path(arguments[index + 1]).expanduser().resolve()
        del arguments[index : index + 2]
    if any(argument.startswith("--") for argument in arguments):
        raise SystemExit(__doc__)
    if len(arguments) not in (1, 2, 3, 4):
        raise SystemExit(__doc__)
    return [Path(argument).expanduser().resolve() for argument in arguments], coverage_path


def coverage_reconciliation_errors(
    coverage: dict[str, Any], obligations: dict[str, Any]
) -> list[str]:
    """Require every handoff entry to be accounted for exactly once."""
    problems: list[str] = []
    coverage_pass: dict[str, str] = {}
    sources = coverage.get("sources", [])
    source_passes = [source.get("pass") for source in sources]
    if len(source_passes) != len(set(source_passes)):
        problems.append("coverage handoff source passes must be unique")
    missing_required = {"global", "decomposed"} - set(source_passes)
    if missing_required:
        problems.append(
            "coverage handoff must include global and decomposed sources; missing "
            f"{sorted(missing_required)}"
        )
    for source_index, source in enumerate(sources):
        pass_name = source.get("pass")
        entries = source.get("external_checks_not_performed", [])
        expected_ids = [f"{pass_name}:{index}" for index in range(1, len(entries) + 1)]
        observed_ids = [entry.get("coverage_id") for entry in entries]
        if observed_ids != expected_ids:
            problems.append(
                f"coverage sources/{source_index}: expected sequential coverage IDs "
                f"{expected_ids}, observed {observed_ids}"
            )
        for coverage_id in observed_ids:
            if coverage_id in coverage_pass:
                problems.append(f"coverage ID appears more than once in handoff: {coverage_id}")
            elif isinstance(coverage_id, str):
                coverage_pass[coverage_id] = pass_name

    assignments: Counter[str] = Counter()
    for obligation in obligations.get("obligations", []):
        obligation_id = obligation.get("obligation_id", "<unknown obligation>")
        coverage_ids = obligation.get("coverage_ids", [])
        expected_reporters: set[str] = set()
        for coverage_id in coverage_ids:
            assignments[coverage_id] += 1
            pass_name = coverage_pass.get(coverage_id)
            if pass_name is None:
                problems.append(f"{obligation_id}: unknown coverage ID {coverage_id!r}")
            else:
                expected_reporters.add(COVERAGE_PROVENANCE[pass_name])

        actual_reporters = set(obligation.get("reported_by", []))
        if coverage_ids:
            missing = expected_reporters - actual_reporters
            extra = actual_reporters - expected_reporters - {"inventory"}
            if missing:
                problems.append(
                    f"{obligation_id}: reported_by drops handoff provenance {sorted(missing)}"
                )
            if extra:
                problems.append(
                    f"{obligation_id}: reported_by has provenance without a coverage ID "
                    f"{sorted(extra)}"
                )
        elif actual_reporters != {"inventory"}:
            problems.append(
                f"{obligation_id}: an obligation without coverage_ids must have "
                "reported_by=['inventory']"
            )

    for omission in obligations.get("coverage_notes", {}).get("known_omissions", []):
        coverage_id = omission.get("coverage_id")
        if coverage_id is None:
            continue
        assignments[coverage_id] += 1
        if coverage_id not in coverage_pass:
            problems.append(f"known omission uses unknown coverage ID {coverage_id!r}")

    for coverage_id in coverage_pass:
        if assignments[coverage_id] == 0:
            problems.append(f"handoff coverage ID was dropped: {coverage_id}")
        elif assignments[coverage_id] > 1:
            problems.append(
                f"handoff coverage ID must be accounted for exactly once: {coverage_id} "
                f"appears {assignments[coverage_id]} times"
            )
    return problems


def references_blind_coverage(obligations: dict[str, Any]) -> bool:
    """Return whether an obligations artifact claims blind-pass provenance."""
    for obligation in obligations.get("obligations", []):
        if obligation.get("coverage_ids"):
            return True
        if set(obligation.get("reported_by", [])) - {"inventory"}:
            return True
    return any(
        omission.get("coverage_id") is not None
        for omission in obligations.get("coverage_notes", {}).get("known_omissions", [])
    )


def fetch_log_errors(
    entries: Any,
    obligation_items: list[dict[str, Any]],
    verification: dict[str, Any],
) -> list[str]:
    """Check usable provenance records, not the appropriateness of a search.

    Query scope and source independence require contextual judgment. The
    advisory safeguard reviewer inspects these alongside the actual activity
    record; neither an unfamiliar query word nor a relationship label voids
    an otherwise structurally valid artifact.
    """
    problems: list[str] = []
    if not isinstance(entries, list):
        return ["citation fetch log: expected an array"]
    obligations = {item["obligation_id"]: item for item in obligation_items}
    logged_used: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"citation fetch log/{index}"
        if not isinstance(entry, dict):
            problems.append(f"{label}: expected an object")
            continue
        missing = FETCH_LOG_FIELDS - entry.keys()
        extra = entry.keys() - FETCH_LOG_FIELDS
        if missing:
            problems.append(f"{label}: missing {sorted(missing)}")
        if extra:
            problems.append(f"{label}: unexpected {sorted(extra)}")
        obligation_id = entry.get("obligation_id")
        obligation = obligations.get(obligation_id)
        if obligation is None:
            problems.append(f"{label}: unknown obligation {obligation_id!r}")
            continue
        kind = entry.get("kind")
        query = entry.get("query")
        url = entry.get("url")
        used = entry.get("used")
        relationship = entry.get("relationship_to_manuscript")
        if kind not in {"search", "fetch"}:
            problems.append(f"{label}: invalid kind {kind!r}")
        if not isinstance(used, bool):
            problems.append(f"{label}: used must be boolean")
        if relationship not in {
            "independent", "same_manuscript", "derivative", "cites_manuscript", "unknown"
        }:
            problems.append(f"{label}: invalid manuscript relationship")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            problems.append(f"{label}: reason must be a nonempty string")
        if kind == "search":
            if not isinstance(query, str) or not query.strip():
                problems.append(f"{label}: search query must be a nonempty string")
            if url is not None:
                problems.append(f"{label}: search url must be null")
            if used is not False:
                problems.append(f"{label}: search used must be false")
            if relationship != "unknown":
                problems.append(f"{label}: search relationship must be unknown")
        elif kind == "fetch":
            if query is not None:
                problems.append(f"{label}: fetch query must be null")
            if not isinstance(url, str) or re.match(r"^https?://", url) is None:
                problems.append(f"{label}: fetch url must be HTTP(S)")
        if kind == "fetch" and used is True and isinstance(url, str):
            logged_used.add(url)

    artifact_used = {
        source["url"]
        for resolution in verification.get("resolutions", [])
        for source in resolution.get("sources", [])
        if source.get("used") is True
    }
    if logged_used != artifact_used:
        problems.append(
            "citation fetch log: used source URLs do not match "
            "external verification"
        )
    return problems


def main() -> int:
    artifact_paths, coverage_path = parse_arguments(sys.argv[1:])

    root = schema_dir()
    common = load(root / "common.schema.json")
    coverage_schema = load(root / "blind-external-coverage.schema.json")
    obligation_schema = load(root / "external-obligations.schema.json")
    verification_schema = load(root / "external-verification.schema.json")
    documents = {
        common["$id"]: common,
        obligation_schema["$id"]: obligation_schema,
        verification_schema["$id"]: verification_schema,
    }
    checker = SchemaChecker(documents)
    obligations = load(artifact_paths[0])
    problems = checker.errors(obligations, obligation_schema, obligation_schema)
    coverage = None
    if coverage_path is not None:
        coverage = load(coverage_path)
        problems.extend(checker.errors(coverage, coverage_schema, coverage_schema))
    if report(problems):
        return 1

    obligation_items = obligations.get("obligations", [])
    ids = [item.get("obligation_id") for item in obligation_items]
    expected = [f"O{index}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        problems.append(f"obligation IDs: expected {expected}, observed {ids}")
    # Missing bibliography data and direct versus contextual attribution are
    # inventory/source-review judgments, not schema failures. Preserve supplied
    # keys/entries; never force the worker to fabricate or relabel a citation.
    if coverage is not None:
        problems.extend(coverage_reconciliation_errors(coverage, obligations))
    elif len(artifact_paths) > 1 and references_blind_coverage(obligations):
        problems.append(
            "full verification of blind-pass coverage requires --coverage-input"
        )

    if len(artifact_paths) == 1:
        if report(problems):
            return 1
        print(f"valid external obligations: obligations={len(ids)}")
        return 0

    verification = load(artifact_paths[1])
    problems.extend(checker.errors(verification, verification_schema, verification_schema))
    if report(problems):
        return 1
    resolutions = verification.get("resolutions", [])
    resolution_ids = [item.get("obligation_id") for item in resolutions]
    if resolution_ids != ids:
        problems.append(
            "resolutions must appear once each and in external-obligation order: "
            f"expected {ids}, observed {resolution_ids}"
        )

    obligation_by_id = {item["obligation_id"]: item for item in obligation_items if "obligation_id" in item}
    resolved_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    for resolution in resolutions:
        obligation_id = resolution.get("obligation_id")
        status = resolution.get("status")
        sources = resolution.get("sources", [])
        checks = resolution.get("checks", [])
        check_statuses = {item.get("status") for item in checks}
        unresolved_checks = resolution.get("unresolved_checks", [])
        has_unresolved_check = "unresolved" in check_statuses
        # A definite mismatch may coexist with open questions. Preserve both
        # the established verdict and incomplete coverage instead of forcing
        # the verifier to discard one of them.
        if has_unresolved_check:
            unresolved_ids.add(obligation_id)
        if bool(unresolved_checks) != has_unresolved_check:
            problems.append(
                f"{obligation_id}: unresolved_checks must be nonempty exactly when "
                "at least one verification check is unresolved"
            )
        check_kinds = [item.get("kind") for item in checks]
        if len(check_kinds) != len(set(check_kinds)):
            problems.append(f"{obligation_id}: duplicate verification check kind")
        obligation = obligation_by_id.get(obligation_id)
        if obligation:
            missing = set(obligation["verification_targets"]) - set(check_kinds)
            if missing:
                problems.append(f"{obligation_id}: missing requested checks {sorted(missing)}")
        used = [source for source in sources if source.get("used") is True]
        finding_ids = resolution.get("finding_ids", [])
        if status == "verified":
            resolved_ids.add(obligation_id)
            if not used:
                problems.append(f"{obligation_id}: verified without a used source")
            if check_statuses - {"satisfied", "not_applicable"}:
                problems.append(f"{obligation_id}: verified with a failed or unresolved check")
            if finding_ids:
                problems.append(f"{obligation_id}: verified resolution cannot link findings")
        elif status == "source_mismatch":
            if not has_unresolved_check:
                resolved_ids.add(obligation_id)
            if not used:
                problems.append(f"{obligation_id}: source_mismatch without a used source")
            if "not_satisfied" not in check_statuses:
                problems.append(f"{obligation_id}: source_mismatch requires a not_satisfied check")
            if not finding_ids:
                problems.append(f"{obligation_id}: source_mismatch must link a verifier finding")
        elif status in {"not_found", "undecidable"}:
            unresolved_ids.add(obligation_id)
            if not has_unresolved_check or not unresolved_checks:
                problems.append(
                    f"{obligation_id}: {status} requires an unresolved check and explanation"
                )
            if status == "not_found" and used:
                problems.append(f"{obligation_id}: not_found cannot use a source as evidence")
            if "not_satisfied" in check_statuses:
                problems.append(
                    f"{obligation_id}: {status} cannot claim a definite source mismatch"
                )

    coverage = verification.get("coverage_notes", {})
    if set(coverage.get("resolved_obligation_ids", [])) != resolved_ids:
        problems.append("coverage resolved_obligation_ids do not match fully resolved checks")
    if set(coverage.get("unresolved_obligation_ids", [])) != unresolved_ids:
        problems.append("coverage unresolved_obligation_ids do not match unresolved checks")

    if len(artifact_paths) == 3:
        fetch_log = load(artifact_paths[2])
        problems.extend(fetch_log_errors(fetch_log, obligation_items, verification))
    elif len(artifact_paths) == 4:
        fetch_log = load(artifact_paths[2])
        problems.extend(fetch_log_errors(fetch_log, obligation_items, verification))
        verifier_output = load(artifact_paths[3])
        actual_findings = {
            item.get("finding_id"): item
            for item in verifier_output.get("findings", [])
            if isinstance(item, dict)
        } if isinstance(verifier_output, dict) else {}
        actual_finding_ids = set(actual_findings)
        linked_finding_ids = {
            finding_id
            for resolution in resolutions
            for finding_id in resolution.get("finding_ids", [])
        }
        if linked_finding_ids != actual_finding_ids:
            problems.append(
                "external verification finding_ids do not match verifier-output findings"
            )
        for resolution in resolutions:
            if resolution.get("status") == "source_mismatch":
                for finding_id in resolution.get("finding_ids", []):
                    if actual_findings.get(finding_id, {}).get("class") == "cosmetic_or_exposition_only":
                        problems.append(
                            f"{resolution['obligation_id']}/{finding_id}: "
                            "source mismatch cannot be exposition-only"
                        )

    if report(problems):
        return 1
    counts = Counter(item["status"] for item in resolutions)
    rendered = ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
    print(f"valid external verification: obligations={len(ids)}; {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
