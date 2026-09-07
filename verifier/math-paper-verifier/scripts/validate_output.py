#!/usr/bin/env python3
"""Validate verifier-output.v1 and severity ordering with the standard library.

Usage: python3 validate_output.py OUTPUT.json [--schema-only]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


SEVERITY = [
    "central_unsalvageable_error",
    "noncentral_unsalvageable_error",
    "major_repairable_gap",
    "minor_repairable_gap",
    "cosmetic_or_exposition_only",
]


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
        type_ok = {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
        }.get(expected, True)
        if not type_ok:
            return problems + [f"{path}: expected {expected}"]

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                problems.append(f"{path}: string is too short")
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                problems.append(f"{path}: does not match {schema['pattern']!r}")
        if isinstance(value, int) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                problems.append(f"{path}: must be at least {schema['minimum']}")

        if isinstance(value, dict):
            for key in schema.get("required", []):
                if key not in value:
                    problems.append(f"{path}: missing required property {key!r}")
            properties = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                for key in value.keys() - properties.keys():
                    problems.append(f"{path}: unexpected property {key!r}")
            for key, child_schema in properties.items():
                if key in value:
                    problems.extend(
                        self.errors(value[key], child_schema, current, f"{path}/{key}")
                    )

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                problems.append(f"{path}: array is too short")
            if schema.get("uniqueItems"):
                encoded = [json.dumps(item, sort_keys=True) for item in value]
                if len(encoded) != len(set(encoded)):
                    problems.append(f"{path}: array items are not unique")
            if "items" in schema:
                for index, item in enumerate(value):
                    problems.extend(
                        self.errors(item, schema["items"], current, f"{path}/{index}")
                    )
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
        if "not" in schema and not self.errors(value, schema["not"], current, path):
            problems.append(f"{path}: forbidden schema matched")
        if "if" in schema and not self.errors(value, schema["if"], current, path):
            problems.extend(self.errors(value, schema.get("then", {}), current, path))
        return problems


def main() -> int:
    argv = [value for value in sys.argv[1:] if value != "--schema-only"]
    schema_only = "--schema-only" in sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit(__doc__)
    target = Path(argv[0]).expanduser().resolve()
    if not target.is_file():
        raise SystemExit(f"no such file: {target}")

    bundle = Path(__file__).resolve().parent.parent
    schema_dir = bundle / "contract"
    if not schema_dir.is_dir():
        schema_dir = bundle / "references" / "schema"
    common = json.loads((schema_dir / "common.schema.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (schema_dir / "verifier-output.schema.json").read_text(encoding="utf-8")
    )
    output = json.loads(target.read_text(encoding="utf-8"))
    checker = SchemaChecker({common["$id"]: common, contract["$id"]: contract})
    problems = checker.errors(output, contract, contract)
    if problems:
        print("schema: INVALID")
        for problem in problems[:20]:
            print(f"  - {problem}")
        if len(problems) > 20:
            print(f"  - ... and {len(problems) - 20} more")
        return 1

    if schema_only:
        print(
            f"valid verifier-output.v1 schema: verdict={output['verdict']}, "
            f"findings={len(output['findings'])}"
        )
        return 0

    order = {name: index for index, name in enumerate(SEVERITY)}
    observed = [order[item["class"]] for item in output["findings"]]
    if observed != sorted(observed):
        print("ranking: INVALID; findings are not ordered most-severe-first")
        return 1

    ids = [item["finding_id"] for item in output["findings"]]
    expected = [f"F{i}" for i in range(1, len(ids) + 1)]
    if ids != expected:
        print(f"finding IDs: INVALID; expected {expected}, observed {ids}")
        return 1

    print(
        f"valid verifier-output.v1: verdict={output['verdict']}, "
        f"findings={len(output['findings'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
