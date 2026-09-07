#!/usr/bin/env python3
"""Check Claude run integrity and surface possible contamination for review.

    python3 run/audit_claude_run.py <run_dir>
    python3 run/audit_claude_run.py <run_dir> --citation-mode

Exit code 1 is reserved for unusable artifacts, process/input integrity failures,
or actual WebFetch/WebSearch use in a blind pass. Path keywords and network-like
shell text are ADVISORY signals, not proof of prohibited behavior. They must not
automatically void or trigger a retry of the mathematical verification.

In --citation-mode, preserve actual web inputs alongside the authored fetch log
for advisory model and human review. Query appropriateness and source
independence are judgment calls, not deterministic word-allowlist checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from audit_codex_run import external_fetch_log_problems

NET_RE = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|rsync|pip3? install|apt(-get)? |"
                    r"git (clone|fetch|pull)|python[3]? -m http)\b|https?://", re.I)
FORBIDDEN_RE = re.compile(r"hidden_gold|paper_history\.json|admitted_errors|"
                          r"gold_annotation|injected_error\.json|erratum_key", re.I)
HIJACK_RE = re.compile(r"SKILL\.md|CLAUDE\.md", re.I)


def audit(run_dir: Path, citation_mode: bool = False) -> int:
    run_dir = run_dir.resolve()
    try:
        run_meta = json.loads((run_dir / "run.json").read_text())
        if not isinstance(run_meta, dict):
            raise ValueError("run.json is not an object")
    except (OSError, ValueError) as exc:
        print(f"INTEGRITY FAILURE: cannot read run.json: {exc}")
        return 1
    sandbox_prefix = run_meta.get("sandbox_dir", "")
    stream = run_dir / "agent.stream.jsonl"
    if not stream.exists():
        print("INTEGRITY FAILURE: no agent.stream.jsonl — no captured machine record")
        return 1

    void: list[str] = []
    advisory: list[str] = []
    web_calls: list[dict] = []
    n_tools = 0

    if not isinstance(sandbox_prefix, str):
        void.append("run.json sandbox_dir is not a string")
        sandbox_prefix = ""
    if run_meta.get("claude_exit") != 0:
        void.append(f"Claude process exit was {run_meta.get('claude_exit')!r}, not 0")
    if run_meta.get("sandbox_input_integrity") is not True:
        void.append("prepared sandbox inputs were missing or changed during the run")
    if run_meta.get("artifact_collected") is not True:
        advisory.append(
            "initial artifact collection failed or was not recorded; compare current "
            "repaired artifacts with the preserved transcript and run the shared "
            "artifact validators. Historical collection metadata has not been changed."
        )
    result_name = run_meta.get("result", "verifier-output.json")
    required_artifacts: set[str] = set()
    if not isinstance(result_name, str) or not result_name:
        void.append(f"invalid result filename {result_name!r} in run.json")
    else:
        required_artifacts.add(result_name)
    declared_artifacts = run_meta.get("artifacts", [])
    if not isinstance(declared_artifacts, list) or any(
        not isinstance(name, str) or not name for name in declared_artifacts
    ):
        void.append("run.json artifacts must be an array of filenames")
    else:
        required_artifacts.update(declared_artifacts)
    pass_name = run_meta.get("requested_pass", run_meta.get("pass"))
    if pass_name == "external-verification":
        required_artifacts.update(("external-verification.json", "citation-fetch-log.json"))
    elif pass_name == "argument-spine":
        required_artifacts.add("argument-spine.json")
    elif pass_name in ("citation", "citation-fidelity"):
        required_artifacts.add("citation-fetch-log.json")
    for artifact_name in sorted(required_artifacts):
        artifact_path = run_dir / artifact_name
        if not artifact_path.is_file():
            void.append(f"missing current required artifact {artifact_name!r}")
            continue
        try:
            artifact = json.loads(artifact_path.read_text())
            expected_type = list if artifact_name == "citation-fetch-log.json" else dict
            if not isinstance(artifact, expected_type):
                raise ValueError(f"expected a JSON {'array' if expected_type is list else 'object'}")
        except (OSError, ValueError) as exc:
            void.append(f"invalid current required artifact {artifact_name!r}: {exc}")

    stream_bytes = stream.read_bytes()
    if "event_stream_sha256" in run_meta and hashlib.sha256(stream_bytes).hexdigest() != run_meta["event_stream_sha256"]:
        void.append("transcript hash does not match run.json")
    malformed_events = 0
    event_count = 0
    for line in stream_bytes.decode(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            malformed_events += 1
            continue
        if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
            malformed_events += 1
            continue
        event_count += 1
        if ev.get("type") != "assistant":
            continue
        message = ev.get("message", {})
        if not isinstance(message, dict) or not isinstance(message.get("content", []), list):
            malformed_events += 1
            continue
        for block in message.get("content", []):
            if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                continue
            n_tools += 1
            name = block.get("name", "")
            inp = block.get("input", {})
            if not isinstance(name, str) or not isinstance(inp, dict):
                malformed_events += 1
                continue
            inp_str = json.dumps(inp, ensure_ascii=False, sort_keys=True)

            if name in ("WebFetch", "WebSearch"):
                if citation_mode:
                    web_calls.append({"tool": name, "input": inp})
                else:
                    void.append(f"{name} in a blind run: {inp_str}")
                continue
            if name == "Bash":
                cmd = str(inp.get("command", ""))
                if NET_RE.search(cmd):
                    advisory.append(f"network-shaped Bash (not proof of network use): {cmd}")
                if FORBIDDEN_RE.search(cmd):
                    advisory.append(f"Bash naming sensitive-looking material: {cmd}")
                continue
            if name in ("Read", "Grep", "Glob"):
                path = str(inp.get("file_path") or inp.get("path") or "")
                if path and sandbox_prefix and not path.startswith(sandbox_prefix) \
                        and path.startswith("/"):
                    if FORBIDDEN_RE.search(path):
                        advisory.append(f"{name} of a sensitive-looking path outside sandbox: {path}")
                    elif HIJACK_RE.search(path):
                        advisory.append(f"{name} of {path} (review instruction exposure)")
                    else:
                        advisory.append(f"{name} outside sandbox: {path}")
            if FORBIDDEN_RE.search(inp_str):
                advisory.append(f"sensitive-looking string in {name} input: {inp_str}")

    if malformed_events:
        void.append(f"event stream contains {malformed_events} malformed JSON line(s)")
    if not event_count:
        void.append("event stream has no usable machine events")

    print("=" * 74)
    print(f"RUN {run_dir.name}   ({n_tools} tool call(s))")
    if citation_mode:
        log = run_dir / "citation-fetch-log.json"
        if not log.exists():
            void.append("citation mode but no citation-fetch-log.json")
        else:
            try:
                entries = json.loads(log.read_text())
                if not isinstance(entries, list):
                    raise ValueError("citation-fetch-log.json is not a JSON array")
                if any(not isinstance(entry, dict) for entry in entries):
                    raise ValueError("citation-fetch-log.json entries must be objects")
            except (OSError, ValueError) as exc:
                entries = []
                void.append(f"invalid citation fetch log: {exc}")
            print("  ~  MODEL-AUTHORED FETCH LOG:")
            for entry in entries:
                print(f"     {json.dumps(entry, ensure_ascii=False, sort_keys=True)}")
                if entry.get("used") and entry.get("relationship_to_manuscript") not in (None, "independent"):
                    advisory.append("used source is labelled "
                                    f"{entry['relationship_to_manuscript']!r}: {entry.get('url')}; "
                                    "review source appropriateness")
            if not entries:
                print("     (no entries)")
            structured_external_mode = (run_dir / "external-obligations.json").is_file() or any(
                "obligation_id" in entry or "relationship_to_manuscript" in entry
                for entry in entries
            )
            if structured_external_mode:
                void.extend(external_fetch_log_problems(run_dir, entries))
        print("  ~  MACHINE-OBSERVED WEB ACTIVITY (provider transcript):")
        for call in web_calls:
            print(f"     {json.dumps(call, ensure_ascii=False, sort_keys=True)}")
        if not web_calls:
            print("     (none extracted; this does not establish absence of network activity)")
        print("  ~  ADVISORY / HUMAN REVIEW: examine actual queries, source relationships, "
              "and authored records. No word allowlist or exact correspondence is "
              "enforced; flags do not automatically void or retry the run.")

    for x in advisory:
        print(f"  ~  ADVISORY  {x}")
    for x in void:
        print(f"  !! VOID      {x}")
    print("=" * 74)
    if void:
        print("INTEGRITY OR ISOLATION CHECK FAILED — inspect the recorded failure.")
        return 1
    print("INTEGRITY CHECKS PASSED — advisory review remains separate; "
          "this is not a certification of appropriate activity.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--citation-mode", action="store_true")
    args = ap.parse_args()
    return audit(args.run_dir, args.citation_mode)


if __name__ == "__main__":
    raise SystemExit(main())
