#!/usr/bin/env python3
"""Validate an ensemble-paper-audit.argument-spine.v1 artifact.

Usage: python3 validate_argument_spine.py ARGUMENT-SPINE.json [VERIFIER-OUTPUT.json]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from validate_external_artifacts import SchemaChecker


EDGE_CHECK_KINDS = {
    "conclusion_match",
    "hypotheses",
    "parameters_and_ranges",
    "normalization",
    "quantifier_order",
    "variable_binding",
    "logical_sufficiency",
}


def sequential_ids(items: list[dict[str, Any]], key: str, prefix: str) -> list[str]:
    observed = [item[key] for item in items]
    expected = [f"{prefix}{index}" for index in range(1, len(items) + 1)]
    if observed == expected:
        return []
    return [f"{key}: expected {expected}, observed {observed}"]


def graph_errors(output: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    claims = output["central_claims"]
    nodes = output["nodes"]
    edges = output["edges"]
    claim_ids = {claim["claim_id"] for claim in claims}
    node_by_id = {node["node_id"]: node for node in nodes}

    problems.extend(sequential_ids(claims, "claim_id", "C"))
    problems.extend(sequential_ids(nodes, "node_id", "N"))
    problems.extend(sequential_ids(edges, "edge_id", "D"))

    roots: set[str] = set()
    for claim in claims:
        root_id = claim["root_node_id"]
        root = node_by_id.get(root_id)
        if root is None:
            problems.append(f"claim {claim['claim_id']}: unknown root node {root_id}")
            continue
        roots.add(root_id)
        if root["kind"] != "central_claim" or root["role"] != "central_claim":
            problems.append(
                f"claim {claim['claim_id']}: root {root_id} must have central_claim kind and role"
            )

    for edge in edges:
        dependency = edge["dependency_node_id"]
        consumer = edge["consumer_node_id"]
        if dependency not in node_by_id:
            problems.append(f"edge {edge['edge_id']}: unknown dependency node {dependency}")
        if consumer not in node_by_id:
            problems.append(f"edge {edge['edge_id']}: unknown consumer node {consumer}")
        if dependency == consumer:
            problems.append(f"edge {edge['edge_id']}: self-dependency is not allowed")
        kinds = [check["kind"] for check in edge["checks"]]
        if set(kinds) != EDGE_CHECK_KINDS or len(kinds) != len(EDGE_CHECK_KINDS):
            problems.append(
                f"edge {edge['edge_id']}: checks must contain each required kind exactly once"
            )
        check_statuses = {check["status"] for check in edge["checks"]}
        edge_status = edge["status"]
        if edge_status == "verified" and check_statuses - {"satisfied", "not_applicable"}:
            problems.append(
                f"edge {edge['edge_id']}: verified edge has an unsatisfied or unresolved check"
            )
        if edge_status in {"repairably_incomplete", "failed"} and (
            "not_satisfied" not in check_statuses or "unresolved" in check_statuses
        ):
            problems.append(
                f"edge {edge['edge_id']}: {edge_status} requires a not_satisfied "
                "check and no unresolved check"
            )
        if edge_status == "unresolved" and (
            "unresolved" not in check_statuses or "not_satisfied" in check_statuses
        ):
            problems.append(
                f"edge {edge['edge_id']}: unresolved requires an unresolved check "
                "and no definite not_satisfied check"
            )

    indegree = {node_id: 0 for node_id in node_by_id}
    consumers: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        dependency = edge["dependency_node_id"]
        consumer = edge["consumer_node_id"]
        if dependency in node_by_id and consumer in node_by_id:
            consumers[dependency].append(consumer)
            indegree[consumer] += 1
    acyclic_queue: deque[str] = deque(
        node_id for node_id, degree in indegree.items() if degree == 0
    )
    visited = 0
    while acyclic_queue:
        node_id = acyclic_queue.popleft()
        visited += 1
        for consumer in consumers[node_id]:
            indegree[consumer] -= 1
            if indegree[consumer] == 0:
                acyclic_queue.append(consumer)
    if visited != len(node_by_id):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        problems.append(f"dependency graph contains a cycle involving {cyclic}")

    reachable_roots: set[str] = set(roots)
    queue: deque[str] = deque(roots)
    dependencies: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        dependencies[edge["consumer_node_id"]].append(edge["dependency_node_id"])
    while queue:
        consumer = queue.popleft()
        for dependency in dependencies[consumer]:
            if dependency not in reachable_roots:
                reachable_roots.add(dependency)
                queue.append(dependency)
    for node_id in node_by_id.keys() - reachable_roots:
        problems.append(f"node {node_id}: not on a dependency path to any central claim")

    coverage = output["coverage_notes"]
    audited = set(coverage["audited_claim_ids"])
    unresolved = set(coverage["unresolved_claim_ids"])
    for unknown in (audited | unresolved) - claim_ids:
        problems.append(f"coverage_notes: unknown claim ID {unknown}")
    expected_unresolved = {
        claim["claim_id"] for claim in claims if claim["status"] == "unresolved"
    }
    if unresolved != expected_unresolved:
        problems.append(
            "coverage_notes/unresolved_claim_ids: must equal claims with unresolved status"
        )
    if audited | unresolved != claim_ids or audited & unresolved:
        problems.append(
            "coverage_notes: audited_claim_ids and unresolved_claim_ids must partition all claims"
        )

    edge_by_consumer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edge_by_consumer[edge["consumer_node_id"]].append(edge)
    for claim in claims:
        stack = [claim["root_node_id"]]
        seen: set[str] = set()
        spine_node_statuses: set[str] = set()
        spine_edge_statuses: set[str] = set()
        while stack:
            node_id = stack.pop()
            if node_id in seen or node_id not in node_by_id:
                continue
            seen.add(node_id)
            spine_node_statuses.add(node_by_id[node_id]["status"])
            for edge in edge_by_consumer[node_id]:
                spine_edge_statuses.add(edge["status"])
                stack.append(edge["dependency_node_id"])

        statuses = spine_node_statuses | spine_edge_statuses
        claim_status = claim["status"]
        if claim_status == "established" and statuses != {"verified"}:
            problems.append(
                f"claim {claim['claim_id']}: established spine contains a non-verified node or edge"
            )
        if claim_status == "repairably_incomplete" and (
            "repairably_incomplete" not in statuses
            or "failed" in statuses
            or "unresolved" in statuses
        ):
            problems.append(
                f"claim {claim['claim_id']}: repairably_incomplete requires a repairable defect and no failed or unresolved dependency"
            )
        if claim_status == "method_breakdown" and "failed" not in statuses:
            problems.append(
                f"claim {claim['claim_id']}: method_breakdown requires a failed node or edge"
            )
        if claim_status == "unresolved" and "unresolved" not in statuses:
            problems.append(
                f"claim {claim['claim_id']}: unresolved requires an unresolved node or edge"
            )

    return problems


def finding_link_errors(output: dict[str, Any], verifier_output: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(verifier_output, dict):
        return ["verifier output: expected an object"]
    linked: set[str] = set()
    for item in output["nodes"] + output["edges"]:
        item_id = item.get("node_id", item.get("edge_id", "<unknown>"))
        finding_ids = item.get("finding_ids", [])
        status = item["status"]
        if status in {"repairably_incomplete", "failed"} and not finding_ids:
            problems.append(f"{item_id}: {status} item must link a verifier finding")
        if status in {"verified", "unresolved"} and finding_ids:
            problems.append(f"{item_id}: {status} item cannot link a verifier finding")
        linked.update(finding_ids)
    actual_findings = {
        item.get("finding_id"): item
        for item in verifier_output.get("findings", [])
        if isinstance(item, dict)
    }
    actual = set(actual_findings)
    if linked != actual:
        problems.append("argument-spine finding_ids do not match verifier-output findings")
    repairable_classes = {"major_repairable_gap", "minor_repairable_gap"}
    failed_classes = {
        "central_unsalvageable_error",
        "noncentral_unsalvageable_error",
    }
    for item in output["nodes"] + output["edges"]:
        item_id = item.get("node_id", item.get("edge_id", "<unknown>"))
        for finding_id in item.get("finding_ids", []):
            finding_class = actual_findings.get(finding_id, {}).get("class")
            if item["status"] == "repairably_incomplete" and finding_class not in repairable_classes:
                problems.append(
                    f"{item_id}/{finding_id}: repairably_incomplete must link a repairable finding"
                )
            if item["status"] == "failed" and finding_class not in failed_classes:
                problems.append(
                    f"{item_id}/{finding_id}: failed must link an unsalvageable finding"
                )
    return problems


def main() -> int:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.is_file():
        raise SystemExit(f"no such file: {target}")

    bundle = Path(__file__).resolve().parent.parent
    schema_dir = bundle / "contract"
    if not schema_dir.is_dir():
        schema_dir = bundle / "references" / "schema"
    common = json.loads((schema_dir / "common.schema.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (schema_dir / "argument-spine.schema.json").read_text(encoding="utf-8")
    )
    output = json.loads(target.read_text(encoding="utf-8"))
    checker = SchemaChecker({common["$id"]: common, contract["$id"]: contract})
    problems = checker.errors(output, contract, contract)
    if not problems:
        problems.extend(graph_errors(output))
    if not problems and len(sys.argv) == 3:
        verifier_path = Path(sys.argv[2]).expanduser().resolve()
        if not verifier_path.is_file():
            raise SystemExit(f"no such file: {verifier_path}")
        verifier_output = json.loads(verifier_path.read_text(encoding="utf-8"))
        problems.extend(finding_link_errors(output, verifier_output))
    if problems:
        print("argument spine: INVALID")
        for problem in problems[:20]:
            print(f"  - {problem}")
        if len(problems) > 20:
            print(f"  - ... and {len(problems) - 20} more")
        return 1

    statuses: dict[str, int] = defaultdict(int)
    for claim in output["central_claims"]:
        statuses[claim["status"]] += 1
    rendered = ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses))
    print(
        f"valid ensemble-paper-audit.argument-spine.v1: "
        f"claims={len(output['central_claims'])}, nodes={len(output['nodes'])}, "
        f"edges={len(output['edges'])}; {rendered}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
