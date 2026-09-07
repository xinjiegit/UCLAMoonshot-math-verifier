#!/usr/bin/env python3
"""Prepare and validate app-hosted verifier workers without a provider CLI.

    python3 run/run_native.py prepare --provider codex --paper paper.tex --pass global --out RUN
    python3 run/run_native.py finalize --run RUN --worker-id ACTUAL_APP_WORKER_ID
    python3 run/run_native.py check --run RUN

Preparation is local only. The app must launch a fresh-context native worker
with worker-prompt.txt, wait for its artifacts, and then finalize the pass. The
helper never invokes codex/claude, reads their credentials, or fabricates a
provider transcript. Python validators and TeX dependency preparation are local
subprocesses, shared with the existing CLI implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import codex_adapter
from common import PASSES, PUBLIC_PASS_METAVAR, SKILL_DIR, snapshot_sandbox_inputs


BASE_LIMITATIONS = [
    "Native workers use the host app's permissions and context controls; the "
    "helper does not enforce an OS read sandbox, disable ambient instructions, "
    "or independently prove worker isolation or absence of web access.",
    "Worker IDs, decomposition records, and model-authored fetch logs are "
    "provenance for review, not a complete machine-recorded tool trace.",
    "Structural validation checks input hashes and artifact contracts, not "
    "mathematical correctness, search appropriateness, or source independence.",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to overwrite a symlink: {path.name}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def required_artifacts(which: str) -> list[str]:
    if which == "external-obligations":
        return ["external-obligations.json"]
    artifacts = ["verifier-output.json"]
    if which == "external-verification":
        artifacts += ["external-verification.json", "citation-fetch-log.json"]
    elif which == "argument-spine":
        artifacts.append("argument-spine.json")
    elif which == "citation":
        artifacts.append("citation-fetch-log.json")
    return artifacts


def local_validator(script: str, paths: list[Path | str]) -> dict[str, Any]:
    command = [sys.executable, str(SKILL_DIR / "scripts" / script), *map(str, paths)]
    process = subprocess.run(
        command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return {
        "validator": script,
        "exit_code": process.returncode,
        "diagnostics": (process.stdout + process.stderr).strip(),
    }


def native_prompt(prompt: str, run: Path, which: str) -> str:
    artifacts = ", ".join(required_artifacts(which))
    preamble = (
        "NATIVE APP WORKER EXECUTION\n"
        "You are one fresh-context verification worker, not the main coordinator.\n"
        "Respect the host's higher-priority instructions and permissions. If "
        "this same skill is automatically loaded, follow its assigned-worker "
        "fast path rather than restarting the full workflow; automatic loading "
        "alone does not invalidate the pass. The shared procedure's request "
        "below to ignore unrelated skills does not override host rules.\n"
        f"Your staged input directory is: {run / 'input'}\n"
        f"Your output directory is: {run}\n"
        "Read only this prompt and the staged input directory. Do not inspect "
        "the surrounding repository, run metadata, other passes, prior reviews, "
        "or the parent conversation. Never change staged input files. Native "
        "app permissions may allow more than this scope; this instruction is "
        "not an OS sandbox. Do not install or launch a provider CLI.\n"
        "Interpret the shared procedure's relative input paths from the staged "
        "input directory. The execution-specific exception is output: write "
        f"{artifacts} directly in the output directory, not in input/. "
        "A request below to emit JSON on stdout means return that same JSON as "
        "your final app message as well as saving the required artifact. Do not "
        "invent a CLI transcript, exit code, or tool events.\n"
    )
    if which == "decomposed":
        preamble += (
            "Every nested region worker must also start with no inherited "
            "conversation history (use fork_turns=\"none\" when that control "
            "is exposed). Give it only the assigned region task, staged "
            "manuscript and contract; never completed sibling reports.\n"
            "If this worker cannot spawn fresh independent workers, do only the "
            "region planning stage and return the explicit plan to the app's "
            "coordinator; do not claim a completed decomposed verification. The "
            "coordinator must schedule fresh per-region workers and then a "
            "fresh reducer, following the shared procedure below. Keep global "
            "pass findings out of all these workers. Save the actual region "
            "assignments, worker IDs, prompts, spans and outputs in the native "
            "decomposition ledger.\n"
        )
    return preamble + "\nSHARED MATHEMATICAL PROCEDURE\n\n" + prompt


def prepare(args: argparse.Namespace) -> int:
    paper = args.paper.expanduser().resolve()
    run = args.out.expanduser().resolve()
    if not paper.exists():
        raise ValueError(f"paper input does not exist: {paper}")
    if run == paper or run in paper.parents or (paper.is_dir() and paper in run.parents):
        raise ValueError("--out must be separate from the manuscript/source directory")
    if args.coverage_input and args.which not in {"external-obligations", "external-verification"}:
        raise ValueError("--coverage-input is only for external inventory or verification")
    codex_adapter.resolve_reference_pdf(args.reference_pdf, paper, args.which)
    if run.exists():
        raise ValueError("--out must be a fresh, nonexistent directory; existing runs are never overwritten")
    # Validate the extra, narrow handoff before creating the run. CLI inventory
    # preparation already validates its handoff; full source verification also
    # needs this record to reconcile coverage IDs, but its worker need not read it.
    source_coverage = None
    if args.which == "external-verification" and args.coverage_input:
        source_coverage = args.coverage_input.expanduser().resolve()
        if not args.obligations:
            raise ValueError("--pass external-verification requires --obligations")
        check = local_validator("validate_external_artifacts.py", [
            args.obligations.expanduser().resolve(), "--coverage-input", source_coverage,
        ])
        if check["exit_code"]:
            raise ValueError("external coverage handoff is invalid: " + check["diagnostics"])
    run.mkdir(parents=True, exist_ok=False)

    def consume(sandbox: Path, prompt: str, metadata: dict, _: dict[str, str]) -> None:
        target = run / "input"
        shutil.move(str(sandbox), target)
        sandbox.parent.rmdir()  # Only this helper's now-empty preparation parent.
        if args.which == "external-verification":
            # CLI metadata is useful to its private maintainer, but the native
            # worker can see its output directory. Do not expose paper paths or
            # a TeX manifest there, even though it is told not to read metadata.
            (run / "source-manifest.json").unlink(missing_ok=True)
            for key in ("paper", "source_manifest", "root_tex", "root_selection"):
                metadata.pop(key, None)
        else:
            metadata.pop("paper", None)
        for key in ("external_obligations", "blind_external_coverage"):
            if key in metadata:
                metadata[key] = {
                    "external_obligations": "external-obligations.json",
                    "blind_external_coverage": "blind-external-coverage.json",
                }[key]
        if source_coverage is not None:
            shutil.copy2(source_coverage, run / "blind-external-coverage.json")
            metadata["blind_external_coverage"] = "blind-external-coverage.json"
            metadata["blind_external_coverage_sha256"] = digest(source_coverage)
        prompt = native_prompt(prompt, run, metadata["pass"])
        (run / "worker-prompt.txt").write_text(prompt, encoding="utf-8")
        sealed_names = ["worker-prompt.txt"]
        for name in ("source-manifest.json", "blind-external-coverage.json"):
            if (run / name).is_file():
                sealed_names.append(name)
        if args.which == "external-verification":
            sealed_names.append("external-obligations.json")
        metadata.update({
            "execution_mode": "native",
            "provider": args.provider,
            "model": None,
            "effort": None,
            "runtime_defaults_inherited": True,
            "event_stream_format": None,
            "isolation": "fresh native worker + staged input (host permissions; not OS-enforced)",
            "input_directory": "input",
            "expected_sandbox_inputs": snapshot_sandbox_inputs(target),
            "expected_run_inputs": {name: digest(run / name) for name in sealed_names},
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "artifacts": required_artifacts(metadata["pass"]),
            "native_worker_id": None,
            "native_transcript": None,
            "native_transcript_sha256": None,
            "native_validation_status": "prepared",
            "audit_limitations": BASE_LIMITATIONS + [
                "No native activity export has been supplied; activity is unobserved, not confirmed clean."
            ],
        })
        write_json(run / "run.json", metadata)

    argv = [
        "--paper", str(paper), "--pass", args.which, "--out", str(run),
        "--sandbox-root", str(run / ".preparation"), "--keep-sandbox", "--prepare-only",
    ]
    for flag, value in (("--root", args.root), ("--focus", args.focus),
                        ("--reference-pdf", args.reference_pdf),
                        ("--prompt-file", args.prompt_file), ("--obligations", args.obligations)):
        if value is not None:
            argv += [flag, str(value)]
    if args.coverage_input and args.which == "external-obligations":
        argv += ["--coverage-input", str(args.coverage_input)]
    codex_adapter.main(argv, prepared_consumer=consume)
    print(f"Prepared native {args.provider} pass: {run}")
    print(f"Launch a fresh app worker with {run / 'worker-prompt.txt'}; no provider CLI is used.")
    return 0


def relative_file(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"invalid run-relative path: {name!r}")
    target = root / relative
    if root.resolve() not in target.resolve().parents or any(
        part.is_symlink() for part in (target, *target.parents) if part != root.parent
        and (part == root or root in part.parents)
    ):
        raise ValueError(f"run file may not be a symlink or escape its directory: {name}")
    return target


def load_run(run: Path) -> dict[str, Any]:
    value = json.loads(relative_file(run, "run.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("execution_mode") != "native":
        raise ValueError("run.json is not a native run")
    if value.get("pass") not in PASSES or value.get("provider") not in {"codex", "claude"}:
        raise ValueError("run.json has an invalid pass or provider")
    if value.get("input_directory") != "input":
        raise ValueError("native input_directory must be 'input'")
    return value


def validate_run(run: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    input_errors: list[str] = []
    for root, field in ((run / "input", "expected_sandbox_inputs"), (run, "expected_run_inputs")):
        expected = metadata.get(field)
        if not isinstance(expected, dict) or not expected:
            input_errors.append(f"missing or malformed {field}")
            continue
        for name, expected_digest in expected.items():
            try:
                path = relative_file(root, name)
                if not path.is_file() or digest(path) != expected_digest:
                    input_errors.append(f"prepared input changed or missing: {field}/{name}")
            except (OSError, ValueError, TypeError) as exc:
                input_errors.append(f"invalid prepared input {name!r}: {exc}")
    try:
        if digest(relative_file(run, "worker-prompt.txt")) != metadata.get("prompt_sha256"):
            input_errors.append("worker-prompt.txt does not match prompt_sha256")
    except (OSError, ValueError) as exc:
        input_errors.append(f"worker prompt is unavailable: {exc}")
    if metadata.get("native_input_integrity_failed"):
        input_errors.append("an earlier finalization observed changed inputs; prepare a fresh run")
    errors.extend(input_errors)

    which = metadata["pass"]
    parsed: dict[str, Any] = {}
    for name in required_artifacts(which):
        try:
            parsed[name] = json.loads(relative_file(run, name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"missing or malformed {name}: {exc}")
    if not errors:
        if which != "external-obligations":
            checks.append(local_validator("validate_output.py", [run / "verifier-output.json"]))
        coverage_args: list[Path | str] = []
        if metadata.get("blind_external_coverage"):
            coverage_args = ["--coverage-input", run / "blind-external-coverage.json"]
        if which == "external-obligations":
            checks.append(local_validator("validate_external_artifacts.py", [
                run / "external-obligations.json", *coverage_args,
            ]))
        elif which == "external-verification":
            checks.append(local_validator("validate_external_artifacts.py", [
                run / "external-obligations.json", run / "external-verification.json",
                run / "citation-fetch-log.json", run / "verifier-output.json", *coverage_args,
            ]))
        elif which == "argument-spine":
            checks.append(local_validator("validate_argument_spine.py", [
                run / "argument-spine.json", run / "verifier-output.json",
            ]))
        elif which == "citation":
            # Legacy citation-fidelity uses a different log shape than the
            # external-obligation protocol. Match its existing structural check.
            log = parsed["citation-fetch-log.json"]
            if not isinstance(log, list) or any(not isinstance(item, dict) for item in log):
                errors.append("citation-fetch-log.json must be an array of objects")
        errors.extend(
            f"{check['validator']}: {check['diagnostics']}"
            for check in checks if check["exit_code"] != 0
        )

    provenance: dict[str, str] = {}
    for name in ("native-workers.json", "decomposition-ledger.json"):
        if not (run / name).exists() and not (run / name).is_symlink():
            continue
        try:
            path = relative_file(run, name)
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("expected a JSON object")
            if name == "native-workers.json":
                if value.get("schema_version") != "native-workers.v1" or not isinstance(value.get("workers"), list):
                    raise ValueError("expected native-workers.v1 with a workers array")
                for worker in value["workers"]:
                    if not isinstance(worker, dict) or any(
                        not isinstance(worker.get(key), str) or not worker[key].strip()
                        for key in ("worker_id", "role")
                    ):
                        raise ValueError("each worker needs its recorded worker_id and role")
            provenance[name] = digest(path)
        except (OSError, ValueError) as exc:
            errors.append(f"malformed {name}: {exc}")

    limitations = list(BASE_LIMITATIONS)
    if metadata.get("native_transcript"):
        try:
            transcript = relative_file(run, metadata["native_transcript"])
            if digest(transcript) != metadata.get("native_transcript_sha256"):
                errors.append("native activity export changed after it was recorded")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"native activity export is unavailable: {exc}")
        limitations.append(
            "An activity export was supplied by the coordinator. Its completeness "
            "and provenance have not been independently verified; it is not a CLI event stream."
        )
    else:
        limitations.append(
            "No native activity export has been supplied; activity is unobserved, not confirmed clean."
        )
    if which == "decomposed" and "decomposition-ledger.json" not in provenance:
        limitations.append("No decomposition ledger was supplied; region-worker execution cannot be audited.")
    return {
        "schema_version": "native-validation.v1",
        "checked_at": now(),
        "status": "invalid" if errors else "valid",
        "exit_code": 1 if errors else 0,
        "input_integrity": not input_errors,
        "errors": errors,
        "checks": checks,
        "provenance_sha256": provenance,
        "limitations": limitations,
    }


def finalize(args: argparse.Namespace) -> int:
    run = args.run.expanduser().resolve()
    metadata = load_run(run)
    worker_id = args.worker_id.strip()
    if not worker_id or len(worker_id) > 512 or "\x00" in worker_id:
        raise ValueError("--worker-id must identify the actual native worker")
    previous_worker = metadata.get("native_worker_id")
    if previous_worker and previous_worker != worker_id:
        raise ValueError("worker ID differs from the recorded run; use a fresh run for a different worker")
    metadata["native_worker_id"] = worker_id
    if args.transcript is not None:
        source = args.transcript.expanduser().resolve()
        if not source.is_file():
            raise ValueError("--transcript must be an existing, genuine native activity export")
        target = relative_file(run, "native-transcript.txt")
        if target.exists() and digest(target) != digest(source):
            raise ValueError("a different native transcript is already recorded; it will not be overwritten")
        if not target.exists():
            shutil.copy2(source, target)
        metadata["native_transcript"] = "native-transcript.txt"
        metadata["native_transcript_sha256"] = digest(target)
    result = validate_run(run, metadata)
    metadata.update({
        "completed_at": now(),
        "native_validation_status": result["status"],
        "sandbox_input_integrity": result["input_integrity"],
        "native_input_integrity_failed": not result["input_integrity"],
        "audit_limitations": result["limitations"],
        "native_provenance_sha256": result["provenance_sha256"],
    })
    write_json(run / "run.json", metadata)
    write_json(run / "native-validation.json", result)
    print(json.dumps(result, indent=2))
    return result["exit_code"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare", help="stage shared inputs/prompts; no provider CLI or authentication")
    preparation.add_argument("--provider", choices=("codex", "claude"), required=True)
    preparation.add_argument("--paper", type=Path, required=True)
    preparation.add_argument("--pass", dest="which", choices=sorted(PASSES), metavar=PUBLIC_PASS_METAVAR, required=True)
    preparation.add_argument("--out", type=Path, required=True)
    preparation.add_argument("--root")
    preparation.add_argument("--reference-pdf", type=Path,
                             help="optional matching compiled PDF for source input")
    preparation.add_argument("--focus")
    preparation.add_argument("--prompt-file", type=Path)
    preparation.add_argument("--obligations", type=Path)
    preparation.add_argument("--coverage-input", type=Path)
    finalization = commands.add_parser("finalize", help="record native worker and validate current artifacts")
    finalization.add_argument("--run", type=Path, required=True)
    finalization.add_argument("--worker-id", required=True)
    finalization.add_argument("--transcript", type=Path, help="optional genuine native export, never a reconstructed transcript")
    checking = commands.add_parser("check", help="recheck current inputs/artifacts without changing the run")
    checking.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            return prepare(args)
        if args.command == "finalize":
            return finalize(args)
        run = args.run.expanduser().resolve()
        metadata = load_run(run)
        if not isinstance(metadata.get("native_worker_id"), str) or not metadata["native_worker_id"].strip():
            raise ValueError("native run is not finalized: record its actual worker with finalize first")
        if metadata.get("native_validation_status") != "valid":
            raise ValueError("native run is not finalized as valid; finalize after repairing its artifacts")
        result = validate_run(run, metadata)
        print(json.dumps(result, indent=2))
        return result["exit_code"]
    except (OSError, ValueError) as exc:
        print(f"native runner: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
