#!/usr/bin/env python3
"""Run one verifier pass on a paper, isolated. Portable (no repo assumptions).

    ./run/run_codex.py --paper /path/to/paper.tex --pass global
    ./run/run_codex.py --paper /path/to/paper.tex --pass decomposed
    ./run/run_codex.py --paper /path/to/paper.tex --pass refuter
    ./run/run_codex.py --paper /path/to/paper.tex --pass focused-sweep --focus "displayed equations"
    ./run/run_codex.py --paper /path/to/paper.tex --pass citation
    ./run/run_codex.py --paper /path/to/paper.tex --pass external-obligations
    ./run/run_codex.py --paper paper.tex --pass external-obligations --coverage-input blind-coverage.json
    ./run/run_codex.py --paper paper.tex --pass external-verification --obligations obligations.json
    ./run/run_codex.py --paper /path/to/paper.tex --pass argument-spine
    ./run/run_codex.py --paper /path/to/paper.tex --pass direct --prompt-file frozen.txt
    ./run/run_codex.py --paper /path/to/tex-source-dir --root main.tex --pass global

WHY THE ISOLATION MATTERS (learned the hard way)
------------------------------------------------
A verifier must not be able to reach anything that reveals the answer. Three
leaks bit us before this script existed:

1. Running with a repo as the working directory: an agentic verifier reads the
   filesystem, and any answer key, prior run output, or notes sitting there is
   fair game. This script therefore builds a sandbox holding ONLY the paper (or
   its allowlisted TeX dependency closure) and the output contract, and runs the
   agent with that as its working root.
2. `codex --sandbox read-only` restricts WRITES, not READS -- an absolute path
   still reads anything on the machine. So the sandbox is a structural
   mitigation, not enforcement: ALWAYS run `run/audit_codex_run.py` on the
   result before trusting it.
3. Ambient skills and user configuration can change the verification procedure.
   This script uses a fresh private CODEX_HOME by default, without copying the
   user's configuration, and attempts to disable discovered user skills.
   Provider-bundled instructions may still be present; this is not a guarantee
   of a completely skill-less process.

Requires: `codex` CLI on PATH and already authenticated (`codex login`).
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
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

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
)


HERE = SKILL_DIR


def repair_invalid_json_backslashes(text: str) -> str:
    """Make odd backslash runs before non-JSON escapes even."""
    out: list[str] = []
    index = 0
    valid = set('"\\/bfnrtu')
    while index < len(text):
        if text[index] != "\\":
            out.append(text[index])
            index += 1
            continue
        end = index
        while end < len(text) and text[end] == "\\":
            end += 1
        count = end - index
        following = text[end] if end < len(text) else ""
        if count % 2 and following not in valid:
            count += 1
        out.append("\\" * count)
        index = end
    return "".join(out)


def codex_jsonl_events(path: Path) -> list[dict[str, object]] | None:
    """Return a complete Codex JSONL stream, or None for a legacy transcript."""
    events: list[dict[str, object]] = []
    for raw_line in path.read_text(errors="replace").splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            return None
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            return None
        events.append(event)
    return events or None


def contract_text(path: Path) -> str:
    """Extract only agent-message payloads from JSONL; support old plain logs."""
    events = codex_jsonl_events(path)
    if events is None:
        return path.read_text(errors="replace")
    messages: list[str] = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if (
            isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            messages.append(item["text"])
    return "\n".join(messages)


def extract_contract_object(
    stdout_path: Path,
    run_dir: Path,
    output_name: str,
    required_keys: tuple[str, ...],
) -> bool:
    """Extract the last matching JSON object, repairing invalid LaTeX escapes."""
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", contract_text(stdout_path))
    # Accept both the historical pretty-printed form, whose closing brace is
    # on its own line, and a complete compact object on one line.  The latter
    # is valid JSON but the old expression could never select it because its
    # closing brace did not begin a line.
    blocks = re.findall(
        r"^\{[^\n]*\}[^\S\n]*$|^\{.*?^\}",
        text,
        re.S | re.M,
    )
    for block in reversed(blocks):
        repaired = False
        candidate = block
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            # Models sometimes place TeX delimiters such as \( and \Delta in
            # JSON strings without escaping the backslash. Double only JSON-
            # invalid escape introducers; leave valid JSON escapes untouched.
            candidate = repair_invalid_json_backslashes(block)
            try:
                obj = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            repaired = candidate != block
        if not isinstance(obj, dict) or not all(key in obj for key in required_keys):
            continue
        (run_dir / output_name).write_text(candidate, encoding="utf-8")
        if repaired:
            (run_dir / "format-repair-note.txt").write_text(
                "Mechanically doubled JSON-invalid backslashes in the final "
                "agent object (for example, TeX \\( delimiters). No other "
                "text or structure was changed.\n",
                encoding="utf-8",
            )
        return True
    return False


def extract_verifier_output(stdout_path: Path, run_dir: Path) -> bool:
    return extract_contract_object(
        stdout_path,
        run_dir,
        "verifier-output.json",
        ("verdict", "findings", "coverage_notes"),
    )


def collect_verifier_output(
    stdout_path: Path,
    sandbox: Path,
    run_dir: Path,
    *,
    allow_sidecar: bool,
) -> bool:
    """Collect stdout output, with an unambiguous writable-sidecar fallback."""
    extracted = extract_verifier_output(stdout_path, run_dir)
    sidecar = sandbox / "verifier-output.json"
    if not allow_sidecar or not sidecar.is_file():
        return extracted
    target = run_dir / "verifier-output.json"
    if not extracted:
        shutil.copy2(sidecar, target)
        return True
    try:
        stdout_value = json.loads(target.read_text(encoding="utf-8"))
        sidecar_value = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if stdout_value != sidecar_value:
        (run_dir / "verifier-output-conflict.txt").write_text(
            "The stdout verifier object and writable verifier-output.json "
            "sidecar differed; the attempt is ambiguous and must be void.\n",
            encoding="utf-8",
        )
        return False
    return True


def extract_external_obligations(stdout_path: Path, run_dir: Path) -> bool:
    return extract_contract_object(
        stdout_path,
        run_dir,
        "external-obligations.json",
        ("schema_version", "obligations", "coverage_notes"),
    )


def ensure_codex_home(
    max_agent_threads: int | None = None,
    requested_home: Path | None = None,
) -> Path:
    """A minimal private CODEX_HOME with auth but no user config or skills."""
    # Do not reuse the legacy ~/.codex-verify home. Older runner versions copied
    # the user's complete config.toml, which can enable plugins and advertise
    # unrelated skills even when skills/ began empty.
    home = (
        requested_home.expanduser().resolve()
        if requested_home is not None
        else Path(tempfile.mkdtemp(prefix="run-", dir=private_runtime_dir("codex-homes")))
    )
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    system_skills = home / "skills" / ".system"
    system_skills.mkdir(parents=True, exist_ok=True)
    # Best-effort suppression for CLI versions that respect this marker. Newer
    # releases may still inject provider-bundled instructions; do not claim a
    # completely skill-less process. No user configuration is copied.
    (system_skills / ".codex-system-skills.marker").touch(exist_ok=True)
    src = Path.home() / ".codex"
    for name in ("auth.json",):
        s, d = src / name, home / name
        # Re-copy auth whenever the main home's copy is newer: OAuth refresh
        # tokens are single-use, so once ~/.codex refreshes, a stale copy here
        # 401s forever ("refresh token was already used"). Measured 2026-08-03.
        stale = name == "auth.json" and d.exists() and s.exists() \
            and s.stat().st_mtime > d.stat().st_mtime
        if s.exists() and (not d.exists() or stale):
            shutil.copy2(s, d)
            if name == "auth.json":
                d.chmod(0o600)
    if not (home / "auth.json").exists():
        sys.exit(f"no credentials at {home/'auth.json'} — run `codex login` first, "
                 f"then re-run (this script copies ~/.codex/auth.json).")

    # Codex also discovers personal skills under ~/.agents/skills independently
    # of CODEX_HOME, and current releases may refresh bundled system skills even
    # when the bootstrap marker exists. Generate a minimal private config that
    # disables every skill visible from either location. Never copy the user's
    # config: it may enable plugins, MCP servers, hooks, or unrelated workflows.
    skill_names: set[str] = set()
    skill_roots = (home / "skills", Path.home() / ".agents" / "skills")
    for root in skill_roots:
        if not root.is_dir():
            continue
        skill_files = set(root.rglob("SKILL.md"))
        # rglob does not descend into top-level symlinked skill directories on
        # all supported Python versions; ~/.agents/skills commonly uses them.
        for child in root.iterdir():
            direct = child / "SKILL.md"
            if direct.is_file():
                skill_files.add(direct)
        for skill_file in skill_files:
            try:
                head = skill_file.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                continue
            match = re.search(r"(?m)^name:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", head)
            if match:
                skill_names.add(match.group(1).strip())
    config = "".join(
        f"[[skills.config]]\nname = {json.dumps(name)}\nenabled = false\n\n"
        for name in sorted(skill_names)
    )
    if max_agent_threads is not None:
        config += (
            "[agents]\n"
            f"max_threads = {max_agent_threads}\n"
        )
    (home / "config.toml").write_text(config, encoding="utf-8")
    return home


def main(
    argv: list[str] | None = None,
    *,
    prepared_consumer: Callable[[Path, str, dict, dict[str, str]], None] | None = None,
) -> int:
    """Launch a pass, or hand the shared local preparation to a native runner.

    The consumer is invoked only with --prepare-only, before any CLI/auth setup.
    It receives the staged directory, complete prompt, metadata, and input hashes.
    Keeping this seam here lets app-hosted workers use precisely the same input
    closure and mathematical prompt as the CLI, without executing the CLI.
    """
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--paper",
        required=True,
        type=Path,
        help="a paper file (.pdf/.tex/.md/.txt) or a multi-file TeX source directory",
    )
    ap.add_argument(
        "--root",
        help="for a TeX source directory, the root .tex path relative to --paper",
    )
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
    ap.add_argument(
        "--prompt-file",
        type=Path,
        help="frozen prompt file (required for --pass direct; read by the runner, "
             "never exposed as a filesystem path to the audit agent)",
    )
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
    ap.add_argument(
        "--effort",
        help="optional reasoning-effort override (default: Codex runtime default)",
    )
    ap.add_argument(
        "--model",
        help="optional model override (default: Codex runtime default)",
    )
    ap.add_argument(
        "--max-agent-threads",
        type=int,
        help="maximum concurrent spawned-agent threads for this isolated run "
             "(default: let Codex choose)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        help="output dir (default ./paper-audit-output/<timestamp>_<pass>_<unique>)",
    )
    ap.add_argument(
        "--sandbox-root",
        type=Path,
        help="throwaway sandbox parent (default: private system temporary directory)",
    )
    ap.add_argument(
        "--codex-home",
        type=Path,
        help="private CODEX_HOME (default: fresh run-specific system temporary directory)",
    )
    ap.add_argument(
        "--allow-web",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--keep-sandbox", action="store_true")
    ap.add_argument(
        "--extract-only",
        action="store_true",
        help="re-extract this pass's stdout artifact from --out/agent.stdout "
             "without launching Codex",
    )
    ap.add_argument(
        "--prepare-only",
        action="store_true",
        help="prepare and record the isolated input, but do not invoke codex",
    )
    args = ap.parse_args(argv)
    if prepared_consumer is not None and not args.prepare_only:
        ap.error("a preparation consumer requires --prepare-only")

    if args.max_agent_threads is not None and args.max_agent_threads < 1:
        sys.exit("--max-agent-threads must be at least 1")

    paper = args.paper.expanduser().resolve()
    if not paper.exists():
        sys.exit(f"paper input does not exist: {paper}")
    if not (paper.is_file() or paper.is_dir()):
        sys.exit(f"paper input is neither a file nor a directory: {paper}")
    if args.root and not paper.is_dir():
        sys.exit("--root is valid only when --paper is a TeX source directory")
    pass_spec = PASSES[args.which]
    prompt_rel, harness = pass_spec.prompt_path, pass_spec.harness
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

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out:
        run_dir = args.out.resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = allocate_sandbox(
            Path.cwd() / "paper-audit-output", stamp, harness
        ).resolve()

    if args.extract_only:
        stdout_path = run_dir / "agent.stdout"
        if not stdout_path.is_file():
            sys.exit(f"no transcript to extract: {stdout_path}")
        if args.which == "external-obligations":
            extracted = extract_external_obligations(stdout_path, run_dir)
            result_path = run_dir / "external-obligations.json"
        else:
            extracted = extract_verifier_output(stdout_path, run_dir)
            result_path = run_dir / "verifier-output.json"
        if extracted:
            print(f"extracted -> {result_path}", file=sys.stderr)
            return 0
        sys.exit("no contract-shaped JSON object found in transcript")

    # Sandbox: ONLY the paper dependency closure + output contract. Copies,
    # never symlinks. A directory is normalized into an allowlisted bundle.
    sandbox_parent = (
        args.sandbox_root.expanduser().resolve()
        if args.sandbox_root
        else private_runtime_dir("sandboxes")
    )
    sandbox = allocate_sandbox(sandbox_parent, stamp, harness)
    (sandbox / "contract").mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "contract/verifier-output.schema.json", sandbox / "contract/verifier-output.schema.json")
    shutil.copy2(HERE / "contract/common.schema.json", sandbox / "contract/common.schema.json")
    shutil.copy2(HERE / "contract/argument-spine.schema.json", sandbox / "contract/argument-spine.schema.json")
    shutil.copy2(HERE / "contract/citation-fetch-log.schema.json", sandbox / "contract/citation-fetch-log.schema.json")
    shutil.copy2(HERE / "contract/external-obligations.schema.json", sandbox / "contract/external-obligations.schema.json")
    shutil.copy2(HERE / "contract/external-verification.schema.json", sandbox / "contract/external-verification.schema.json")
    shutil.copy2(HERE / "contract/blind-external-coverage.schema.json", sandbox / "contract/blind-external-coverage.schema.json")
    shutil.copy2(HERE / "references/output-contract.md", sandbox / "contract/output-contract.md")
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
    input_metadata: dict[str, object]
    expected_sandbox_inputs: dict[str, str] = {}
    if paper.is_dir():
        source_dir = sandbox / "source"
        prepare_cmd = [
            sys.executable,
            str(HERE / "run/prepare_latex_bundle.py"),
            str(paper),
            "--out",
            str(source_dir),
        ]
        if args.root:
            prepare_cmd += ["--root", args.root]
        prepared = subprocess.run(
            prepare_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if prepared.returncode:
            if prepared.stdout:
                print(prepared.stdout, file=sys.stderr, end="")
            if prepared.stderr:
                print(prepared.stderr, file=sys.stderr, end="")
            if not args.keep_sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            sys.exit(
                "TeX source preparation failed; resolve the reported root or "
                "required dependencies before auditing"
            )
        manifest_path = source_dir / "source-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_sandbox_inputs["source/source-manifest.json"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        for entry in manifest["files"]:
            expected_sandbox_inputs[f"source/{entry['path']}"] = entry["sha256"]
        shutil.copy2(manifest_path, run_dir / "source-manifest.json")
        unresolved = manifest["unresolved"]
        if withhold_paper:
            shutil.rmtree(source_dir)
            expected_sandbox_inputs.clear()
            prompt += (
                "\n\nThe manuscript is deliberately withheld from this retrieval "
                "stage. Use only ./external-obligations.json for paper claims, "
                "use sites, and locations. Do not search for or identify the "
                "manuscript. The output contract is in ./contract/.\n"
            )
        else:
            prompt += (
                "\n\nPaper source bundle: ./source/\n"
                "Read ./source/source-manifest.json first. Begin at its root_tex, "
                "follow the document's logical include order, and read ONLY files "
                "listed in the manifest. Use relative source paths in every region "
                "span and evidence reference. In each finding, put the relative "
                "path in location.source_file and the section title in location.section. "
                "Record unresolved "
                "manifest entries in coverage_notes.\n"
                "Do not compile TeX, run build files, or execute code from the paper. "
                "Inspect the staged paper inputs only.\n"
                "The output contract is in ./contract/. Everything you need is in "
                "this directory; do not look outside it.\n"
            )
        sha = manifest["aggregate_sha256"]
        paper_size = sum(item["bytes"] for item in manifest["files"])
        input_metadata = {
            "paper_input_kind": "tex_source_bundle",
            "source_manifest": "source-manifest.json",
            "root_tex": manifest["root_tex"],
            "root_selection": manifest["root_selection"],
            "source_file_count": len(manifest["files"]),
            "unresolved_dependency_count": len(unresolved),
            "agent_paper_access": not withhold_paper,
        }
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
            expected_sandbox_inputs.update(prepared_paper.expected_files)
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
        expected_sandbox_inputs.update(compiled.expected_files)
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
        expected_sandbox_inputs["external-obligations.json"] = hashlib.sha256(
            obligations_path.read_bytes()
        ).hexdigest()
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
                    and note.get("coverage_id")
                    == f"{item['pass']}:{index}"
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
        expected_sandbox_inputs["blind-external-coverage.json"] = hashlib.sha256(
            coverage_path.read_bytes()
        ).hexdigest()
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

    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
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
        "schema_version": "run.v1", "harness": harness,
        "pass": pass_spec.resolved_selector,
        "requested_pass": args.which,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "paper": str(paper), "paper_sha256": sha, "paper_chars": paper_size,
        "provider": "codex", "model": args.model, "effort": args.effort,
        "runtime_defaults_inherited": args.model is None and args.effort is None,
        "prompt_source_sha256": prompt_source_sha256,
        "prompt_sha256": prompt_sha256,
        "focus_specification": focus_specification,
        "focus_sha256": (
            hashlib.sha256(focus_specification.encode("utf-8")).hexdigest()
            if focus_specification is not None
            else None
        ),
        "max_agent_threads": args.max_agent_threads,
        "web_search": args.which if web_enabled else "disabled",
        "event_stream_format": "codex_exec_jsonl_v1",
        "isolation": "staged inputs + private user configuration; provider system instructions may remain",
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
        if prepared_consumer is not None:
            prepared_consumer(sandbox, prompt, run_metadata, expected_sandbox_inputs)
            return 0
        print(f"prepared: {run_dir}", file=sys.stderr)
        if paper.is_dir():
            print(
                f"root    : {input_metadata['root_tex']} "
                f"({input_metadata['source_file_count']} file(s), "
                f"{input_metadata['unresolved_dependency_count']} unresolved)",
                file=sys.stderr,
            )
        if not args.keep_sandbox:
            shutil.rmtree(sandbox, ignore_errors=True)
        return 0

    # Persistent sessions are needed by child-agent startup in Codex 0.153.x.
    # Keep each run's home separate; persistence does not mean sharing context.
    cmd = ["codex", "exec", "--json", "-C", str(sandbox), "--skip-git-repo-check",
           "--ignore-rules", "-c", "features.multi_agent=true", "-c", "features.apps=false"]
    if args.effort is not None:
        cmd += ["-c", f"model_reasoning_effort={args.effort}"]
    if args.model is not None:
        cmd += ["-m", args.model]
    needs_sidecar_write = args.which == "argument-spine"
    if web_enabled:
        cmd += ["--sandbox", "workspace-write", "-c", 'web_search="live"']
    elif needs_sidecar_write:
        cmd += ["--sandbox", "workspace-write", "-c", 'web_search="disabled"']
    else:
        cmd += ["--sandbox", "read-only", "-c", 'web_search="disabled"']
    cmd.append(prompt)

    env = dict(os.environ)
    # A runner launched from inside Codex Desktop otherwise inherits the parent
    # task identity. That can make app-only skills appear in a nominally
    # isolated CLI child. Detach the child before assigning its private home.
    for name in (
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        "CODEX_CI",
    ):
        env.pop(name, None)
    env["CODEX_HOME"] = str(
        ensure_codex_home(args.max_agent_threads, args.codex_home)
    )
    run_metadata.update(session_persistence=True, codex_home=env["CODEX_HOME"],
                        launch_arguments=cmd[:-1])
    overrides = ", ".join(
        item for item in (
            f"model={args.model}" if args.model else "",
            f"effort={args.effort}" if args.effort else "",
        ) if item
    ) or "Codex runtime defaults"
    print(f"run     : {run_dir}\nsandbox : {sandbox}\npaper   : {paper.name} "
          f"(sha {sha[:12]}…)\npass    : {pass_spec.resolved_selector} @ {overrides}", file=sys.stderr)

    stdout_path = run_dir / "agent.stdout"
    stderr_path = run_dir / "agent.stderr"
    with stdout_path.open("wb") as stdout_fh, stderr_path.open("wb") as stderr_fh:
        rc = subprocess.run(
            cmd,
            stdout=stdout_fh,
            stderr=stderr_fh,
            stdin=subprocess.DEVNULL,
            env=env,
        ).returncode
    sessions = Path(env["CODEX_HOME"]) / "sessions"
    if sessions.is_dir():
        # Only transcript records, never auth/configuration files, enter output.
        shutil.copytree(sessions, run_dir / "sessions", dirs_exist_ok=True)
        run_metadata["session_records"] = "sessions/"
    run_metadata.update({
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "codex_exit": rc,
        "event_stream_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
        "sandbox_input_integrity": sandbox_inputs_intact(
            sandbox, expected_sandbox_inputs
        ),
    })
    (run_dir / "run.json").write_text(
        json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"codex exit: {rc}", file=sys.stderr)

    # Extract only when the exact sandbox inputs prepared for this call still
    # exist. A missing/replaced sandbox can otherwise yield a valid-looking
    # result about a different concurrently audited paper.
    if not run_metadata["sandbox_input_integrity"]:
        artifact_ok = False
        result_path = run_dir / (
            "external-obligations.json"
            if args.which == "external-obligations"
            else "verifier-output.json"
        )
        print(
            "!! sandbox inputs disappeared or changed during the model call; "
            "the attempt is void",
            file=sys.stderr,
        )
    elif args.which == "external-obligations":
        artifact_ok = extract_external_obligations(stdout_path, run_dir)
        result_path = run_dir / "external-obligations.json"
    else:
        artifact_ok = collect_verifier_output(
            stdout_path,
            sandbox,
            run_dir,
            allow_sidecar=args.which in {"argument-spine", "external-verification"},
        )
        result_path = run_dir / "verifier-output.json"
    if artifact_ok:
        print(f"collected -> {result_path}", file=sys.stderr)
    else:
        print("!! no contract-shaped JSON object found in the transcript; inspect agent.stdout",
              file=sys.stderr)

    if web_enabled:
        fetch_log = sandbox / "citation-fetch-log.json"
        if fetch_log.exists():
            shutil.copy2(fetch_log, run_dir / "citation-fetch-log.json")
        else:
            print("!! no citation-fetch-log.json; web run is not auditable", file=sys.stderr)
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
    if not args.keep_sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)

    print("\nNEXT (all listed checks are required before trusting the result):",
          file=sys.stderr)
    print(
        f"  python3 run/audit_codex_run.py {run_dir}"
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
