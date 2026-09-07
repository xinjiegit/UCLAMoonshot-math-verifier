#!/usr/bin/env python3
"""Run one verifier pass on a paper, isolated — CLAUDE engine variant.

    ./run/run_claude_code.py --paper /path/to/paper.tex --pass global
    ./run/run_claude_code.py --paper /path/to/paper.tex --pass decomposed
    ./run/run_claude_code.py --paper /path/to/tex-source-dir --root main.tex --pass global
    ./run/run_claude_code.py --paper paper.tex --pass focused-sweep --focus "displayed equations" --allow-compute
    ./run/run_claude_code.py --paper paper.tex --pass citation
    ./run/run_claude_code.py --paper paper.tex --pass external-obligations --coverage-input coverage.json
    ./run/run_claude_code.py --paper paper.tex --pass external-verification --obligations obligations.json
    ./run/run_claude_code.py --paper paper.tex --pass argument-spine
    ./run/run_claude_code.py --paper paper.tex --pass direct --prompt-file frozen.txt

The engine is `claude -p` (Claude Code headless).

ISOLATION MODEL (differs from codex — read before trusting results)
-------------------------------------------------------------------
- Sandbox: identical idea — a throwaway dir holding ONLY the paper (or its
  allowlisted TeX closure) + the output contract; the agent runs with it as
  cwd. Reads elsewhere are possible in principle, so the audit gate is
  mandatory, exactly as with codex.
- Network: codex enforces web-off in its sandbox. Claude Code cannot fully
  sandbox `Bash` networking, so blind passes here get NO Bash tool at all
  (allowed tools: Read, Grep, Glob, Task) — the main passes never needed to
  compute (measured). Sweeps may enable Bash with --allow-compute; the gate
  then flags network-shaped commands for advisory review. WebFetch/WebSearch are disallowed
  except for registry-declared source-verification passes, where web access is
  enabled automatically.
- Transcript: the run captures --output-format stream-json (every tool call is
  an event), which is what makes the gate mechanical. Do not switch formats.
- Residual (parallel to codex known-issue #7): user-level ~/.claude skills and
  CLAUDE.md remain visible to the child; every pass prompt opens with an
  ignore-external-instructions rule, and the gate flags SKILL.md reads.

Requires: `claude` CLI on PATH, logged in. Tokens are spent on YOUR Claude
account (Claude both orchestrates and verifies in this variant).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common import (
    COVERAGE_SOURCE_PASSES,
    PASSES,
    PUBLIC_PASS_METAVAR,
    SKILL_DIR,
    allocate_sandbox,
    append_focus_specification,
    append_location_guidance,
    pass_requires_web,
    prepare_single_paper,
    prepare_reference_pdf,
    private_runtime_dir,
    resolve_focus_specification,
    resolve_reference_pdf,
    sandbox_inputs_intact,
    snapshot_sandbox_inputs,
)


HERE = SKILL_DIR
BLIND_TOOLS = "Read Grep Glob Task TodoWrite"
COMPUTE_TOOLS = BLIND_TOOLS + " Bash"
WEB_TOOLS = BLIND_TOOLS + " WebFetch WebSearch Write"
SIDECAR_TOOLS = BLIND_TOOLS + " Write"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paper", required=True, type=Path,
                    help="a paper file (.pdf/.tex/.md/.txt) or a multi-file TeX source directory")
    ap.add_argument("--root", help="for a TeX source dir, the root .tex relative to --paper")
    ap.add_argument("--reference-pdf", type=Path,
                    help="optional matching compiled PDF for reader-facing locations with source input")
    ap.add_argument(
        "--pass",
        dest="which",
        required=True,
        choices=sorted(PASSES),
        metavar=PUBLIC_PASS_METAVAR,
    )
    ap.add_argument(
        "--focus",
        help="required for --pass focused-sweep; e.g. 'displayed equations', "
             "'boundary clauses', or another precise audit axis",
    )
    ap.add_argument("--prompt-file", type=Path,
                    help="frozen prompt file (required for --pass direct)")
    ap.add_argument(
        "--obligations",
        type=Path,
        help="validated external-obligations.json (required for "
             "--pass external-verification)",
    )
    ap.add_argument(
        "--coverage-input",
        type=Path,
        help="sealed global/decomposed external-check notes (valid only for "
             "--pass external-obligations)",
    )
    ap.add_argument("--model", help="optional model override (default: Claude runtime default)")
    ap.add_argument("--effort", help="optional effort override (default: Claude runtime default)")
    ap.add_argument(
        "--out",
        type=Path,
        help="output dir (default ./paper-audit-output/<timestamp>_<pass>_<unique>)",
    )
    ap.add_argument("--sandbox-root", type=Path,
                    help="throwaway sandbox parent (default: private system temporary directory)")
    ap.add_argument("--allow-web", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--allow-compute", action="store_true",
                    help="focused sweep: enable Bash (python/sympy). The gate flags "
                         "network-shaped commands; blind main passes should NOT use this.")
    ap.add_argument("--keep-sandbox", action="store_true")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()

    paper = args.paper.expanduser().resolve()
    if not paper.exists():
        sys.exit(f"paper input does not exist: {paper}")
    if args.root and not paper.is_dir():
        sys.exit("--root is valid only when --paper is a TeX source directory")
    pass_spec = PASSES[args.which]
    prompt_rel, harness = pass_spec.prompt_path, pass_spec.harness
    resolved_pass = pass_spec.resolved_selector
    try:
        focus_specification = resolve_focus_specification(args.which, args.focus)
        reference_pdf = resolve_reference_pdf(args.reference_pdf, paper, args.which)
    except ValueError as exc:
        sys.exit(str(exc))
    if args.which == "direct" and not args.prompt_file:
        sys.exit("--pass direct requires --prompt-file")
    if args.which != "direct" and args.prompt_file:
        sys.exit("--prompt-file is only valid with --pass direct")
    web_enabled = pass_requires_web(args.which)
    if args.allow_web and not web_enabled:
        sys.exit("--allow-web is deprecated and valid only for a registry-declared web pass")
    if args.which == "external-verification" and not args.obligations:
        sys.exit("--pass external-verification requires --obligations")
    if args.which != "external-verification" and args.obligations:
        sys.exit("--obligations is valid only with --pass external-verification")
    if args.coverage_input and args.which != "external-obligations":
        sys.exit("--coverage-input is valid only with --pass external-obligations")
    if args.allow_compute and resolved_pass != "focused-sweep":
        sys.exit("--allow-compute is valid only with --pass focused-sweep")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out:
        run_dir = args.out.resolve()
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            sys.exit(f"output directory already exists: {run_dir}")
    else:
        runs_parent = Path.cwd() / "paper-audit-output"
        runs_parent.mkdir(parents=True, exist_ok=True)
        run_dir = allocate_sandbox(runs_parent, stamp, harness)

    sandbox_parent = (
        args.sandbox_root.expanduser().resolve()
        if args.sandbox_root
        else private_runtime_dir("sandboxes")
    )
    sandbox = allocate_sandbox(sandbox_parent, stamp, harness)
    (sandbox / "contract").mkdir(parents=True, exist_ok=True)
    for name in (
        "argument-spine.schema.json",
        "blind-external-coverage.schema.json",
        "citation-fetch-log.schema.json",
        "common.schema.json",
        "external-obligations.schema.json",
        "external-verification.schema.json",
        "verifier-output.schema.json",
    ):
        shutil.copy2(HERE / "contract" / name, sandbox / "contract" / name)
    shutil.copy2(
        HERE / "references/output-contract.md",
        sandbox / "contract/output-contract.md",
    )
    shutil.copy2(HERE / "references/finding-locations.md", sandbox / "contract/finding-locations.md")

    prompt_path = (args.prompt_file.expanduser().resolve()
                   if args.prompt_file else HERE / prompt_rel)
    if not prompt_path.is_file():
        sys.exit(f"prompt file does not exist: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8")
    prompt_source_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    prompt = append_focus_specification(prompt, focus_specification)
    prompt = append_location_guidance(prompt, args.which)
    withhold_paper = args.which == "external-verification"
    expected_sandbox_inputs: dict[str, str] = {}
    if paper.is_dir():
        source_dir = sandbox / "source"
        prepared = subprocess.run(
            [sys.executable, str(HERE / "run/prepare_latex_bundle.py"), str(paper),
             "--out", str(source_dir)] + (["--root", args.root] if args.root else []),
            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if prepared.returncode:
            print(prepared.stdout + prepared.stderr, file=sys.stderr, end="")
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit("TeX source preparation failed")
        manifest_path = source_dir / "source-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shutil.copy2(manifest_path, run_dir / "source-manifest.json")
        if withhold_paper:
            shutil.rmtree(source_dir)
            prompt += (
                "\n\nThe manuscript is deliberately withheld from this retrieval "
                "stage. Use only ./external-obligations.json for paper claims, "
                "use sites, and locations. Do not search for or identify the "
                "manuscript. The output contract is in ./contract/.\n"
            )
        else:
            prompt += ("\n\nPaper source bundle: ./source/\n"
                       "Read ./source/source-manifest.json first. Begin at its root_tex, "
                       "follow the document's logical include order, and read ONLY files "
                       "listed in the manifest. Use relative source paths in every region "
                       "span and evidence reference; put the relative path in location.source_file "
                       "and the section title in location.section. Record unresolved manifest entries in coverage_notes.\n"
                       "Do not compile TeX, run build files, or execute code from the paper.\n"
                       "The output contract is in ./contract/. Everything you need is in "
                       "this directory; do not look outside it.\n")
        sha = manifest["aggregate_sha256"]
        paper_size = sum(item["bytes"] for item in manifest["files"])
        input_metadata = {"paper_input_kind": "tex_source_bundle",
                          "root_tex": manifest["root_tex"],
                          "source_file_count": len(manifest["files"]),
                          "agent_paper_access": not withhold_paper}
    else:
        if withhold_paper:
            prompt += (
                "\n\nThe manuscript is deliberately withheld from this retrieval "
                "stage. Use only ./external-obligations.json for paper claims, "
                "use sites, and locations. Do not search for or identify the "
                "manuscript. The output contract is in ./contract/.\n"
            )
        else:
            prepared_paper = prepare_single_paper(paper, sandbox)
            prompt += prepared_paper.prompt_suffix
        if withhold_paper:
            sha = hashlib.sha256(paper.read_bytes()).hexdigest()
            paper_size = len(paper.read_bytes())
            input_metadata = {
                "paper_input_kind": "single_file",
                "agent_paper_access": False,
            }
        else:
            sha = prepared_paper.paper_sha256
            paper_size = prepared_paper.paper_size
            input_metadata = prepared_paper.metadata

    if reference_pdf is not None:
        compiled = prepare_reference_pdf(reference_pdf, sandbox)
        prompt += compiled.prompt_suffix
        input_metadata.update(compiled.metadata)

    if args.obligations:
        obligations_path = args.obligations.expanduser().resolve()
        if not obligations_path.is_file():
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit(f"external obligations do not exist: {obligations_path}")
        validation = subprocess.run(
            [
                sys.executable,
                str(HERE / "scripts/validate_external_artifacts.py"),
                str(obligations_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if validation.returncode:
            if validation.stdout:
                print(validation.stdout, file=sys.stderr, end="")
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit("external obligations failed validation")
        shutil.copy2(obligations_path, sandbox / "external-obligations.json")
        shutil.copy2(obligations_path, run_dir / "external-obligations.json")
        input_metadata["external_obligations"] = str(obligations_path)
        input_metadata["external_obligations_sha256"] = hashlib.sha256(
            obligations_path.read_bytes()
        ).hexdigest()

    if args.coverage_input:
        coverage_path = args.coverage_input.expanduser().resolve()
        if not coverage_path.is_file():
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit(f"blind external coverage does not exist: {coverage_path}")
        try:
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit(f"cannot load blind external coverage: {exc}")
        sources = coverage.get("sources") if isinstance(coverage, dict) else None
        source_passes = {
            item.get("pass") for item in sources if isinstance(item, dict)
        } if isinstance(sources, list) else set()
        valid_coverage = (
            isinstance(coverage, dict)
            and set(coverage) == {"schema_version", "manuscript_id", "run_id", "sources"}
            and coverage.get("schema_version")
            == "ensemble-paper-audit.blind-external-coverage.v1"
            and isinstance(coverage.get("manuscript_id"), str)
            and re.fullmatch(r"ms_[a-z0-9_]+", coverage["manuscript_id"])
            and isinstance(coverage.get("run_id"), str)
            and re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", coverage["run_id"])
            and isinstance(sources, list)
            and 2 <= len(sources) <= 4
            and {"global", "decomposed"}.issubset(source_passes)
            and len(source_passes) == len(sources)
            and all(
                item.get("pass") in COVERAGE_SOURCE_PASSES
                for item in sources
                if isinstance(item, dict)
            )
            and all(
                isinstance(item, dict)
                and set(item)
                == {"pass", "output_sha256", "external_checks_not_performed"}
                and isinstance(item.get("output_sha256"), str)
                and re.fullmatch(r"[a-f0-9]{64}", item["output_sha256"])
                and isinstance(item.get("external_checks_not_performed"), list)
                and all(
                    isinstance(note, dict)
                    and set(note) == {"coverage_id", "note"}
                    and note.get("coverage_id") == f"{item['pass']}:{index}"
                    and isinstance(note.get("note"), str)
                    and note["note"].strip()
                    for index, note in enumerate(
                        item["external_checks_not_performed"], 1
                    )
                )
                for item in sources
            )
        )
        if not valid_coverage:
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit("blind external coverage failed its locked input contract")
        shutil.copy2(coverage_path, sandbox / "blind-external-coverage.json")
        shutil.copy2(coverage_path, run_dir / "blind-external-coverage.json")
        rendered_source_passes = ", ".join(item["pass"] for item in sources)
        prompt += (
            "\n\nA sealed narrow handoff from these web-disabled passes is in "
            f"./blind-external-coverage.json: {rendered_source_passes}. It contains "
            "only their coverage_notes.external_checks_not_performed entries with "
            "stable coverage IDs, and no findings or verdicts. Account for every "
            "coverage ID exactly once: put it in one obligation's coverage_ids, or "
            "in one coverage_notes.known_omissions object with a concrete reason. "
            "For an obligation, reported_by must contain exactly the reporting "
            "passes named by its coverage IDs, mapping argument-spine to "
            "argument_spine; add inventory only if the end-to-end inventory also "
            "identified it independently. Obligations found only by the inventory "
            "use coverage_ids=[] and reported_by=[\"inventory\"].\n"
        )
        input_metadata["blind_external_coverage"] = str(coverage_path)
        input_metadata["blind_external_coverage_sha256"] = hashlib.sha256(
            coverage_path.read_bytes()
        ).hexdigest()

    tools = (WEB_TOOLS if web_enabled
             else SIDECAR_TOOLS if args.which == "argument-spine"
             else COMPUTE_TOOLS if args.allow_compute else BLIND_TOOLS)
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    expected_sandbox_inputs = snapshot_sandbox_inputs(sandbox)
    artifacts = ["verifier-output.json"]
    if args.which == "external-obligations":
        artifacts = ["external-obligations.json"]
        if args.coverage_input:
            artifacts.append("blind-external-coverage.json")
    elif args.which == "external-verification":
        artifacts += ["external-verification.json", "citation-fetch-log.json"]
    elif args.which == "argument-spine":
        artifacts.append("argument-spine.json")
    elif args.which == "citation":
        artifacts.append("citation-fetch-log.json")
    run_metadata = {
        "schema_version": "run.v1", "harness": harness, "pass": resolved_pass,
        "requested_pass": args.which,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "paper": str(paper), "paper_sha256": sha, "paper_chars": paper_size,
        "provider": "claude", "model": args.model, "effort": args.effort,
        "runtime_defaults_inherited": args.model is None and args.effort is None,
        "prompt_source_sha256": prompt_source_sha256,
        "prompt_sha256": prompt_sha256,
        "focus_specification": focus_specification,
        "focus_sha256": (
            hashlib.sha256(focus_specification.encode("utf-8")).hexdigest()
            if focus_specification is not None
            else None
        ),
        "allowed_tools": tools,
        "web_search": args.which if web_enabled else "disabled",
        "event_stream_format": "claude_stream_json_v1",
        "isolation": "sandbox_dir + tool allowlist (no Bash on blind passes); "
                     "gate on stream-json transcript is MANDATORY",
        "sandbox_dir": str(sandbox),
        "result": (
            "external-obligations.json"
            if args.which == "external-obligations"
            else "verifier-output.json"
        ),
        "artifacts": artifacts,
        **input_metadata,
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8"
    )

    if args.prepare_only:
        print(f"prepared: {run_dir}", file=sys.stderr)
        if not args.keep_sandbox:
            shutil.rmtree(sandbox, ignore_errors=True)
        return 0

    # Permission mode "default" is the enforcement (measured 2026-08-11):
    # under bypassPermissions the allowlist only pre-approves — the init event
    # showed Bash/Edit still available. In headless default mode, tools not
    # covered by allowedTools are auto-DENIED (no one to prompt), which is
    # what makes the blind allowlist real. disallowedTools additionally
    # REMOVES web tools from the session entirely (verified live: server-side
    # web counters 0).
    if web_enabled:
        denied = "Edit NotebookEdit"
    elif args.which == "argument-spine":
        denied = "WebFetch WebSearch Edit NotebookEdit"
    else:
        denied = "WebFetch WebSearch Edit Write NotebookEdit"
    cmd = ["claude", "-p", prompt]
    if args.model is not None:
        cmd += ["--model", args.model]
    if args.effort is not None:
        cmd += ["--effort", args.effort]
    cmd += ["--allowedTools", tools,
           "--disallowedTools", denied.strip(),
           "--permission-mode", "default",
           "--verbose", "--output-format", "stream-json"]
    overrides = ", ".join(
        item for item in (
            f"model={args.model}" if args.model else "",
            f"effort={args.effort}" if args.effort else "",
        ) if item
    ) or "Claude runtime defaults"
    print(f"run     : {run_dir}\nsandbox : {sandbox}\npaper   : {paper.name} "
          f"(sha {sha[:12]}…)\npass    : {resolved_pass} @ {overrides}", file=sys.stderr)

    # Extended thinking counts toward the per-response output cap; the default
    # 64k killed a live run mid-emission (2026-08-11). Raise it.
    env = dict(os.environ)
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "128000")

    stream_path = run_dir / "agent.stream.jsonl"
    with stream_path.open("wb") as fh:
        rc = subprocess.run(cmd, cwd=sandbox, stdout=fh, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env).returncode
    print(f"claude exit: {rc}", file=sys.stderr)

    input_integrity = sandbox_inputs_intact(sandbox, expected_sandbox_inputs)
    run_metadata.update({
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "claude_exit": rc,
        "event_stream_sha256": hashlib.sha256(stream_path.read_bytes()).hexdigest(),
        "sandbox_input_integrity": input_integrity,
    })

    # Final text: prefer the terminal "result" event; else concatenate
    # assistant text events. Then extract the contract JSON from it.
    final_text = ""
    assistant_chunks: list[str] = []
    for line in stream_path.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result" and isinstance(ev.get("result"), str):
            final_text = ev["result"]
        elif ev.get("type") == "assistant":
            for block in (ev.get("message") or {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    assistant_chunks.append(block.get("text", ""))
    final_text = final_text or "\n".join(assistant_chunks)
    (run_dir / "agent.final.txt").write_text(final_text, encoding="utf-8")

    blocks = re.findall(r"^\{[^\n]*\}[^\S\n]*$|^\{.*?^\}", final_text, re.S | re.M)
    chosen = None
    required_keys = (
        ("schema_version", "obligations", "coverage_notes")
        if args.which == "external-obligations"
        else ("verdict", "findings", "coverage_notes")
    )
    result_name = (
        "external-obligations.json"
        if args.which == "external-obligations"
        else "verifier-output.json"
    )
    for block in reversed(blocks):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and all(key in obj for key in required_keys):
            chosen = block
            break
    artifact_ok = input_integrity and chosen is not None
    if not input_integrity:
        print("!! sandbox inputs disappeared or changed during the model call; "
              "the attempt is void", file=sys.stderr)
    elif chosen:
        (run_dir / result_name).write_text(chosen, encoding="utf-8")
        print(f"extracted -> {run_dir/result_name}", file=sys.stderr)
    else:
        print("!! no contract-shaped JSON found; inspect agent.final.txt / agent.stream.jsonl",
              file=sys.stderr)
    if web_enabled:
        fetch_log = sandbox / "citation-fetch-log.json"
        if fetch_log.exists():
            shutil.copy2(fetch_log, run_dir / "citation-fetch-log.json")
        else:
            print("!! no citation-fetch-log.json; web run is not auditable",
                  file=sys.stderr)
            artifact_ok = False
    if args.which == "external-verification":
        sidecar = sandbox / "external-verification.json"
        if sidecar.exists():
            shutil.copy2(sidecar, run_dir / "external-verification.json")
        else:
            print("!! no external-verification.json sidecar", file=sys.stderr)
            artifact_ok = False
    if args.which == "argument-spine":
        sidecar = sandbox / "argument-spine.json"
        if sidecar.exists():
            shutil.copy2(sidecar, run_dir / "argument-spine.json")
        else:
            print("!! no argument-spine.json sidecar", file=sys.stderr)
            artifact_ok = False
    run_metadata["artifact_collected"] = artifact_ok
    (run_dir / "run.json").write_text(
        json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8"
    )
    if not args.keep_sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)

    print("\nNEXT (all listed checks are required before trusting the result):",
          file=sys.stderr)
    print(
        f"  python3 run/audit_claude_run.py {run_dir}"
        f"{' --citation-mode' if web_enabled else ''}",
        file=sys.stderr,
    )
    if args.which == "external-obligations":
        coverage_suffix = (
            f" --coverage-input {run_dir}/blind-external-coverage.json"
            if args.coverage_input
            else ""
        )
        print(
            f"  python3 scripts/validate_external_artifacts.py "
            f"{run_dir}/external-obligations.json{coverage_suffix}",
            file=sys.stderr,
        )
    elif args.which == "external-verification":
        print(
            f"  python3 scripts/validate_external_artifacts.py "
            f"{run_dir}/external-obligations.json "
            f"{run_dir}/external-verification.json "
            f"{run_dir}/citation-fetch-log.json "
            f"{run_dir}/verifier-output.json",
            file=sys.stderr,
        )
        print(
            f"  python3 scripts/validate_output.py {run_dir}/verifier-output.json",
            file=sys.stderr,
        )
    elif args.which == "argument-spine":
        print(
            f"  python3 scripts/validate_argument_spine.py "
            f"{run_dir}/argument-spine.json {run_dir}/verifier-output.json",
            file=sys.stderr,
        )
        print(
            f"  python3 scripts/validate_output.py {run_dir}/verifier-output.json",
            file=sys.stderr,
        )
    else:
        print(
            f"  python3 scripts/validate_output.py {run_dir}/verifier-output.json",
            file=sys.stderr,
        )
    print("\nADVISORY REVIEW (flags/unavailability do not trigger a verifier rerun):", file=sys.stderr)
    print(f"  python3 {HERE / 'run/run_safeguard_review.py'} --run {run_dir}", file=sys.stderr)
    if args.which != "external-obligations":
        print(
            f"  python3 scripts/render_report.py {run_dir}/verifier-output.json",
            file=sys.stderr,
        )
    return rc if rc else (0 if artifact_ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
