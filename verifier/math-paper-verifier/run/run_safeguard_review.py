#!/usr/bin/env python3
"""One bounded advisory assessment, partitioned when activity exceeds one packet.

python3 run/run_safeguard_review.py --run RUN_DIRECTORY [--model MODEL]

Uses the audited run's provider, unless --provider is specified. Writes
safeguard-review.json/.md and a preserved input/reviewer transcript directory.
Exit 0 means the advisory was recorded (possibly unavailable), not that the
audited run passed its integrity gate. No verifier reruns or automatic retries.

For an app-native run, --native prepares a packet and prompt for a fresh app
subagent without launching a provider CLI. Then --native --review-response FILE
--reviewer-id ID records that subagent's JSON reply against the prepared packet.
An app-native run selects this path automatically; absent replies stay unavailable.
Large native preparations use one fresh reviewer per part and an ordered JSON
response bundle; see references/safeguard-review.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import SKILL_DIR
from safeguard_packets import encoded as encode_packet, partition

DEFAULT_MODELS = {"codex": "gpt-5.6-luna", "claude": "haiku"}
SCHEMA = SKILL_DIR / "contract/safeguard-review.schema.json"
PROMPT = SKILL_DIR / "references/safeguard-review.txt"
SIDECARS = ("external-obligations.json", "citation-fetch-log.json", "external-verification.json")
NATIVE_DOCUMENTS = SIDECARS + (
    "verifier-output.json", "native-validation.json", "worker-prompt.txt",
    "native-workers.json", "decomposition-ledger.json", "argument-spine.json",
    "blind-external-coverage.json",
)
OUTPUT_FIELDS = {"aggregated_output", "output", "stdout", "stderr", "content", "text"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def clip_outputs(value: Any, clipped: list[str], location: str = "") -> Any:
    """Keep complete tool inputs; bound only potentially enormous tool outputs."""
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            pointer = f"{location}/{key}"
            if key in {"input", "arguments", "action", "query", "queries", "url", "urls", "command"}:
                result[key] = child
            elif key in OUTPUT_FIELDS and isinstance(child, str) and len(child) > 2000:
                result[key] = child[:1000] + "\n[OUTPUT CLIPPED]\n" + child[-1000:]
                clipped.append(pointer)
            else:
                result[key] = clip_outputs(child, clipped, pointer)
        return result
    if isinstance(value, list):
        return [clip_outputs(child, clipped, f"{location}/{i}") for i, child in enumerate(value)]
    return value


def activity_records(raw: str, artifact: str) -> tuple[list[dict], list[str]]:
    """Keep raw structured tool records, including unfamiliar event shapes.

    We do not reconstruct a query/URL allowlist from provider-specific fields.
    Agent prose and reasoning are excluded so they cannot spoof machine events.
    """
    records, clipped = [], []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        location = f"line {number}"
        try:
            event = json.loads(line)
        except ValueError:
            records.append({"artifact": artifact, "location": location, "record": line})
            continue
        if not isinstance(event, dict):
            records.append({"artifact": artifact, "location": location, "record": event})
            continue
        kind = event.get("type")
        if kind in {"thread.started", "turn.started", "turn.completed", "result"}:
            continue
        if kind == "system" and event.get("subtype") == "init":
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "reasoning"}:
            continue
        if kind in {"assistant", "user"}:
            message = event.get("message")
            blocks = message.get("content", []) if isinstance(message, dict) else []
            if not isinstance(blocks, list):
                continue
            blocks = [block for block in blocks if isinstance(block, dict)
                      and block.get("type") not in {"text", "thinking", "redacted_thinking"}]
            if not blocks:
                continue
            event = {"type": kind, "content": blocks}
        records.append({"artifact": artifact, "location": location,
                        "record": clip_outputs(event, clipped, f"{artifact}:{location}")})
    limitations = []
    if clipped:
        limitations.append(f"Tool output excerpts were clipped at {len(clipped)} fields; "
                           "complete tool inputs and the original transcript remain recorded.")
    if not records:
        limitations.append("No tool activity records were recognized; inspect the original transcript.")
    return records, limitations


def build_packet(run: Path, provider: str) -> tuple[dict, list[dict]]:
    metadata_path = run / "run.json"
    metadata_raw = metadata_path.read_bytes()
    metadata = json.loads(metadata_raw)
    if not isinstance(metadata, dict):
        raise ValueError("run.json must be a JSON object")
    audited_provider = metadata.get("provider", provider)
    if audited_provider not in DEFAULT_MODELS:
        raise ValueError(f"unknown audited provider in run.json: {audited_provider!r}")
    if metadata.get("execution_mode") == "native":
        return build_native_packet(run, metadata, metadata_raw)
    transcript = run / ("agent.stdout" if audited_provider == "codex" else "agent.stream.jsonl")
    transcript_raw = transcript.read_bytes()
    activity, limitations = activity_records(transcript_raw.decode("utf-8", errors="replace"), transcript.name)
    if metadata.get("session_records"):
        limitations.append(
            "Additional provider session records are retained under sessions/ for manual inspection. "
            "This packet uses the CLI event stream, which may omit child-agent tool activity; "
            "it does not establish complete child activity coverage."
        )
    artifacts = [{"path": metadata_path.name, "sha256": digest(metadata_raw)},
                 {"path": transcript.name, "sha256": digest(transcript_raw)}]
    documents = {}
    for name in SIDECARS:
        path = run / name
        if path.is_file():
            raw = path.read_bytes()
            artifacts.append({"path": name, "sha256": digest(raw)})
            documents[name] = json.loads(raw)
    gate = SKILL_DIR / "run" / f"audit_{audited_provider}_run.py"
    cmd = [sys.executable, str(gate), str(run)]
    if metadata.get("web_search") not in (None, False, "disabled") or "citation-fetch-log.json" in documents:
        cmd.append("--citation-mode")
    checked = subprocess.run(cmd, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    return {
        "run": {key: metadata[key] for key in
                ("provider", "pass", "harness", "web_search", "sandbox_dir", "paper", "paper_sha256",
                 "paper_input_kind", "agent_paper_access", "source_manifest", "root_tex",
                 "sandbox_input_integrity", "isolation", "session_records")
                if key in metadata},
        "activity": activity,
        "documents": documents,
        "integrity_gate": {"exit_code": checked.returncode,
                           "diagnostics": checked.stdout + checked.stderr},
        "limitations": limitations,
    }, artifacts


def run_artifact(run: Path, relative: str) -> Path:
    """Resolve recorded artifact paths only within this run directory."""
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"artifact path must be relative to the run: {relative!r}")
    path = (run / candidate).resolve()
    if not path.is_relative_to(run.resolve()):
        raise ValueError(f"artifact path escapes the run: {relative!r}")
    return path


def build_native_packet(run: Path, metadata: dict, metadata_raw: bytes) -> tuple[dict, list[dict]]:
    """Review native artifacts without inventing a CLI event stream.

    A genuine export can be plain text, structured JSON, or partial observations.
    Keep it as supplied and label its provenance/completeness as unverified;
    model-authored artifacts are never promoted to machine-observed evidence.
    """
    if (metadata.get("native_validation_status") != "valid"
            or not isinstance(metadata.get("native_worker_id"), str)
            or not metadata["native_worker_id"].strip()):
        raise ValueError("Finalize the native worker with its actual ID and valid artifacts before preparing its safeguard review")
    artifacts = [{"path": "run.json", "sha256": digest(metadata_raw)}]
    documents: dict[str, Any] = {}
    limitations = list(metadata.get("audit_limitations", []))
    limitations.extend([
        "App-native execution: worker isolation, tool restrictions, and activity completeness "
        "are not established by CLI subprocess controls or a machine event stream.",
        "Authored artifacts record the worker's claims, not independently observed tool activity. "
        "Missing activity evidence must not be interpreted as a clean review.",
    ])
    names = list(NATIVE_DOCUMENTS)
    declared = metadata.get("artifacts", [])
    if not isinstance(declared, list) or any(not isinstance(name, str) for name in declared):
        raise ValueError("native artifacts metadata must be an array of run-relative paths")
    names.extend(declared)
    # The staged obligations identify the source worker's assigned task even if
    # it omitted or changed its authored root-level copy.
    for path in sorted((run / "input").glob("*.json")):
        if path.name in {"external-obligations.json", "coverage-input.json", "coverage.json", "blind-external-coverage.json"}:
            names.append(path.relative_to(run).as_posix())
    for name in dict.fromkeys(names):
        path = run_artifact(run, name)
        if path.is_file():
            raw = path.read_bytes()
            artifacts.append({"path": name, "sha256": digest(raw)})
            documents[name] = json.loads(raw) if path.suffix == ".json" else raw.decode("utf-8", errors="replace")
    activity = []
    transcript = metadata.get("native_transcript")
    if transcript:
        if not isinstance(transcript, str):
            raise ValueError("native_transcript must be a relative artifact path or null")
        path = run_artifact(run, transcript)
        raw = path.read_bytes()
        artifacts.append({"path": transcript, "sha256": digest(raw)})
        activity.append({
            "artifact": transcript,
            "location": "complete supplied export; original line numbers preserved in text",
            "provenance": "operator-supplied native export; authenticity and completeness not independently verified",
            "record": raw.decode("utf-8", errors="replace"),
        })
        limitations.append(
            "The supplied native activity export is preserved verbatim, but its authenticity, "
            "coverage, and tool restrictions are not independently verified. It may be partial; "
            "absence of a recorded event does not establish that it did not occur."
        )
    else:
        limitations.append(
            "No native activity export was supplied. The reviewer can assess the worker prompt "
            "and authored artifacts, but cannot independently check actual searches, file access, "
            "or cross-worker communication."
        )
    cmd = [sys.executable, str(SKILL_DIR / "run/run_native.py"), "check", "--run", str(run)]
    checked = subprocess.run(cmd, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    return {
        "run": {key: metadata[key] for key in
                ("provider", "execution_mode", "pass", "harness", "web_search", "paper_sha256",
                 "native_worker_id", "native_validation_status", "native_transcript", "audit_limitations",
                 "model", "effort", "runtime_defaults_inherited", "isolation")
                if key in metadata},
        "activity": activity,
        "documents": documents,
        "integrity_gate": {"exit_code": checked.returncode,
                           "diagnostics": checked.stdout + checked.stderr,
                           "scope": "native artifact and prepared-input integrity only; not CLI process isolation"},
        "limitations": list(dict.fromkeys(limitations)),
    }, artifacts


def reviewer_command(provider: str, model: str, sandbox: Path) -> list[str]:
    if provider == "codex":
        return ["codex", "exec", "--json", "-C", str(sandbox), "--skip-git-repo-check",
                "--ignore-rules", "--ephemeral", "--sandbox", "read-only", "-m", model,
                "-c", 'web_search="disabled"', "-c", "tools.web_search=false",
                "-c", "features.shell_tool=false", "-c", "features.multi_agent=false",
                "-c", "features.js_repl=false", "-c", "features.apps=false",
                "-c", "features.plugins=false", "-c", 'approval_policy="never"',
                "-c", 'model_reasoning_effort="low"', "--output-schema", str(SCHEMA), "-"]
    # Claude's CLI schema validator does not load the 2020-12 meta-schema.
    # This response uses only common object/array/string constraints, so omit
    # the dialect annotation while preserving every constraint.
    claude_schema = json.loads(SCHEMA.read_text())
    claude_schema.pop("$schema", None)
    return ["claude", "--print", "--model", model, "--tools", "", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands",
            "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
            "--no-session-persistence", "--verbose", "--output-format", "stream-json",
            "--json-schema", json.dumps(claude_schema)]


def parse_response(raw: str, provider: str) -> dict:
    messages = []
    structured = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("reviewer emitted a non-object event")
        # Providers can emit a transient reconnect error and then complete.
        # Only a failed turn/result (or absence of a usable final result) makes
        # the advisory unavailable.
        if event.get("type") == "turn.failed" or event.get("is_error") is True:
            raise ValueError("reviewer reported a provider error")
        if provider == "codex":
            item = event.get("item") or {}
            if not isinstance(item, dict):
                raise ValueError("reviewer emitted a malformed item")
            if item.get("type") in {"command_execution", "web_search", "mcp_tool_call", "file_change", "collab_tool_call"}:
                raise ValueError("reviewer attempted tool use instead of reviewing the supplied packet")
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
        else:
            message = event.get("message")
            blocks = message.get("content", []) if isinstance(message, dict) else []
            for block in blocks if isinstance(blocks, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    # Claude's schema response is emitted through a synthetic output tool.
                    if block.get("name") != "StructuredOutput":
                        raise ValueError("reviewer attempted tool use")
                if isinstance(block, dict) and block.get("type") == "text":
                    messages.append(block.get("text", ""))
            if event.get("type") == "result":
                structured = event.get("structured_output")
                if isinstance(event.get("result"), str) and event["result"].strip():
                    messages.append(event["result"])
    if isinstance(structured, dict):
        return structured
    if not messages:
        raise ValueError("reviewer returned no final response")
    text = messages[-1].strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    return json.loads(text)


def failure_detail(record_dir: Path) -> str:
    """Surface a provider's terminal error without dumping its startup state."""
    path = record_dir / "agent.stdout"
    if path.is_file():
        for line in reversed(path.read_text(errors="replace").splitlines()):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result" and event.get("is_error") is True:
                return str(event.get("result", "Provider reported an error"))[:600]
            if event.get("type") == "turn.failed":
                return str(event.get("error", "Provider turn failed"))[:600]
    return "Inspect the captured reviewer stdout/stderr."


def validate_response(response: dict, packet: dict) -> list[str]:
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    from validate_external_artifacts import SchemaChecker
    schema = json.loads(SCHEMA.read_text())
    errors = SchemaChecker({}).errors(response, schema, schema)
    if errors:
        raise ValueError("invalid advisory response: " + "; ".join(errors[:5]))
    # Preserve questionable citations for the human, rather than discarding the
    # whole advisory because of an excerpt-format mismatch.
    limitations = []
    supplied: dict[str, str] = {}
    if "run" in packet:
        supplied["run.json"] = json.dumps(packet["run"], ensure_ascii=False, separators=(",", ":"))
    for record in packet["activity"]:
        supplied[record["artifact"]] = supplied.get(record["artifact"], "") + json.dumps(record["record"], ensure_ascii=False, separators=(",", ":"))
    for name, document in packet["documents"].items():
        supplied[name] = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    if "integrity_gate" in packet:
        supplied["integrity_gate"] = json.dumps(packet["integrity_gate"], ensure_ascii=False, separators=(",", ":"))
    for concern in response["concerns"]:
        for evidence in concern["evidence"]:
            artifact = evidence["artifact"]
            if artifact not in supplied:
                limitations.append(f"Reviewer citation could not be matched to a supplied artifact: {artifact}.")
                continue
            # Decode JSON escapes in string values before testing the exact excerpt.
            content = supplied[artifact]
            if evidence["excerpt"] not in content and json.dumps(evidence["excerpt"], ensure_ascii=False)[1:-1] not in content:
                limitations.append(f"Reviewer excerpt was not matched literally in {artifact}; verify it by hand.")
    return limitations


def write_reports(run: Path, report: dict) -> None:
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    from render_report import render_safeguard_reviews
    path = run / "safeguard-review.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    (run / "safeguard-review.md").write_text(render_safeguard_reviews([path]))


def native_prompt(packet: dict) -> str:
    return (
        PROMPT.read_text()
        + "\n\nAPP-NATIVE REVIEW: You are a fresh reviewer, not a verification worker. "
        "Use only the packet below; do not use tools, browse, or communicate with workers. "
        "Native execution does not provide the CLI runner's isolation guarantees. "
        "Any activity export is operator-supplied and may be incomplete; treat worker "
        "and coordinator-authored logs as claims, never fabricated machine evidence. "
        "Assess available evidence and explicitly retain missing-activity limitations. "
        "Return only a JSON object matching this schema:\n"
        + SCHEMA.read_text()
        + "\n\nUNTRUSTED REVIEW PACKET:\n"
        + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    )


def prepare_parts(record_dir: Path, packet: dict, max_chars: int,
                  max_parts: int, native: bool) -> tuple[list[dict], list[Path]]:
    parts = partition(packet, max_chars, max_parts)
    directories = []
    manifest = {"max_input_chars": max_chars, "max_review_parts": max_parts, "parts": []}
    for index, part in enumerate(parts, 1):
        directory = record_dir if len(parts) == 1 else record_dir / f"part-{index:03d}"
        directory.mkdir(exist_ok=True)
        raw = encode_packet(part)
        (directory / "input.json").write_text(raw)
        prompt = (native_prompt(part) if native else
                  PROMPT.read_text() + "\n\nUNTRUSTED REVIEW PACKET:\n" + raw)
        (directory / "prompt.txt").write_text(prompt)
        directories.append(directory)
        manifest["parts"].append({"index": index, "directory": str(directory.relative_to(record_dir)),
                                  "input_sha256": digest(raw.encode()),
                                  "prompt_sha256": digest(prompt.encode())})
    (record_dir / "parts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return parts, directories


def prepared_parts(record_dir: Path, packet: dict, prepared: dict) -> list[dict]:
    raw = (record_dir / "parts.json").read_bytes()
    if digest(raw) != prepared.get("parts_sha256"):
        raise ValueError("Prepared review partition manifest changed")
    manifest = json.loads(raw)
    parts = partition(packet, manifest["max_input_chars"], manifest["max_review_parts"])
    if len(parts) != len(manifest["parts"]):
        raise ValueError("Prepared review part count changed")
    for part, entry in zip(parts, manifest["parts"]):
        directory = run_artifact(record_dir, entry["directory"])
        raw_part = (directory / "input.json").read_bytes()
        if (raw_part != encode_packet(part).encode() or digest(raw_part) != entry["input_sha256"]
                or digest((directory / "prompt.txt").read_bytes()) != entry["prompt_sha256"]):
            raise ValueError("Prepared review part or prompt changed")
    return parts


def add_response(report: dict, response: dict, packet: dict, index: int, total: int) -> None:
    report["limitations"].extend(validate_response(response, packet))
    report["limitations"].extend(response["limitations"])
    report["concerns"].extend(response["concerns"])
    report.setdefault("part_summaries", []).append({"part": index, "summary": response["summary"]})
    report["reviewed_parts"] = len(report["part_summaries"])
    if total > 1:
        report["limitations"].append(
            "The activity was reviewed in separate bounded packets; cross-packet relationships "
            "may be missed. All recorded concerns are retained without voting or suppression.")
    report["summary"] = (response["summary"] if total == 1 else
                         "\n".join(f"Part {p['part']}/{total}: {p['summary']}" for p in report["part_summaries"]))


def native_review(run: Path, provider: str, model: str | None = None,
                  max_input_chars: int = 240000, review_response: Path | None = None,
                  reviewer_id: str | None = None, max_review_parts: int = 8) -> dict:
    """Prepare or ingest an app subagent's advisory, without invoking a CLI.

    A response is accepted only against the exact saved preparation packet and
    unchanged input artifacts. Identity and isolation are operator-recorded,
    never authenticated by the helper. No reviewer means unavailable, not clean.
    """
    record_dir: Path | None = None
    packet: dict = {}
    report = {
        "schema_version": "ensemble-paper-audit.safeguard-review.v1",
        "status": "unavailable", "provider": provider,
        "model": model or "not recorded (app-selected)",
        "execution_mode": "native", "reviewer_execution_mode": "native",
        "reviewer_id": reviewer_id or "", "run_directory": str(run),
        "input_sha256": "", "reviewed_artifacts": [], "record_directory": "",
        "summary": "Native advisory review unavailable; an independent app reviewer is still needed.",
        "concerns": [], "limitations": [],
    }
    try:
        metadata = json.loads((run / "run.json").read_text())
        if metadata.get("execution_mode") != "native":
            raise ValueError("--native requires an app-native run; it cannot relabel a CLI run")
        if review_response is None:
            root = run / "safeguard-reviews"
            root.mkdir(exist_ok=True)
            record_dir = Path(tempfile.mkdtemp(prefix="review-", dir=root))
            report["record_directory"] = str(record_dir.relative_to(run))
            packet, report["reviewed_artifacts"] = build_packet(run, provider)
            encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
            (record_dir / "input.json").write_text(encoded)
            report["input_sha256"] = digest(encoded.encode())
            report["limitations"] = list(packet["limitations"])
            report["integrity_gate_exit_code"] = packet["integrity_gate"]["exit_code"]
            # Preserve a standalone prompt even for unavailable preparation, but
            # do not dispatch it until the integrity/packet-size checks succeed.
            (record_dir / "prompt.txt").write_text(native_prompt(packet))
            if report["integrity_gate_exit_code"]:
                raise ValueError("Native artifacts failed their integrity check; the advisory cannot make them valid.")
            parts, _ = prepare_parts(record_dir, packet, max_input_chars, max_review_parts, True)
            report["planned_parts"] = len(parts)
            report["reviewed_parts"] = 0
            report["parts_sha256"] = digest((record_dir / "parts.json").read_bytes())
            if len(parts) > 1:
                (record_dir / "prompt.txt").write_text(
                    "Do not dispatch this index as a review task. Give each part-*/prompt.txt "
                    "to a separate fresh reviewer. See parts.json and safeguard-review.md.\n")
            report["native_preparation_ready"] = True
            report["summary"] = "Native review packet prepared; no independent reviewer response has been recorded."
            report["limitations"].append("Preparation only: no independent app reviewer has completed this assessment.")
        else:
            prepared = json.loads((run / "safeguard-review.json").read_text())
            if (prepared.get("reviewer_execution_mode") != "native"
                    or prepared.get("native_preparation_ready") is not True):
                raise ValueError("No usable native preparation exists; prepare the packet before dispatching a reviewer.")
            relative = prepared.get("record_directory", "")
            record_dir = run_artifact(run, relative)
            if record_dir.parent != (run / "safeguard-reviews").resolve():
                record_dir = None
                raise ValueError("Invalid native preparation record directory")
            report["record_directory"] = relative
            raw = (record_dir / "input.json").read_bytes()
            if digest(raw) != prepared.get("input_sha256"):
                raise ValueError("Prepared review packet changed; its recorded fingerprint does not match.")
            packet = json.loads(raw)
            report["input_sha256"] = digest(raw)
            report["reviewed_artifacts"] = prepared["reviewed_artifacts"]
            report["limitations"] = list(packet["limitations"])
            report["integrity_gate_exit_code"] = packet["integrity_gate"]["exit_code"]
            if report["integrity_gate_exit_code"]:
                raise ValueError("The prepared run failed its integrity check")
            parts = prepared_parts(record_dir, packet, prepared)
            report["planned_parts"] = len(parts)
            report["reviewed_parts"] = 0
            for artifact in report["reviewed_artifacts"]:
                if digest(run_artifact(run, artifact["path"]).read_bytes()) != artifact["sha256"]:
                    raise ValueError("Audited artifacts changed after preparation; prepare a fresh review packet.")
            current, current_artifacts = build_packet(run, provider)
            if current["integrity_gate"]["exit_code"]:
                raise ValueError("Native input/artifact integrity failed after preparation")
            if current_artifacts != report["reviewed_artifacts"]:
                raise ValueError("The native artifact inventory changed after preparation; prepare a fresh review packet.")
            worker_ids = {packet["run"].get("native_worker_id")}
            workers = packet["documents"].get("native-workers.json", {})
            if isinstance(workers, dict):
                worker_ids.update(worker.get("worker_id") for worker in workers.get("workers", [])
                                  if isinstance(worker, dict) and isinstance(worker.get("worker_id"), str))
            response_raw = review_response.read_bytes()
            (record_dir / "native-response.json").write_bytes(response_raw)
            response = json.loads(response_raw)
            replies = ([{"part": 1, "reviewer_id": reviewer_id, "response": response}]
                       if len(parts) == 1 else response.get("reviews", []))
            if (not isinstance(replies, list) or any(not isinstance(r, dict) for r in replies)
                    or any(type(r.get("part")) is not int or not 1 <= r["part"] <= len(parts)
                           for r in replies)):
                raise ValueError("Supply responses with valid prepared part numbers")
            numbers = [r["part"] for r in replies]
            if numbers != sorted(set(numbers)):
                raise ValueError("Supply at most one response per prepared part, in part order")
            identities = []
            for reply in replies:
                identity = reply.get("reviewer_id")
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError("--reviewer-id (or each batch reviewer_id) must record the fresh app subagent's actual identifier")
                identity = identity.strip()
                if identity in worker_ids or identity in identities:
                    raise ValueError("Each safeguard reviewer must be a different app subagent from every verification worker and other reviewer")
                identities.append(identity)
            report["reviewer_id"] = identities[0] if len(identities) == 1 else ""
            report["reviewer_ids"] = identities
            report["response_sha256"] = digest(response_raw)
            for reply in replies:
                index = reply["part"]
                add_response(report, reply["response"], parts[index - 1], index, len(parts))
            report["limitations"].append(
                "Native reviewer identity and no-tool-use instructions are operator-recorded, "
                "not independently authenticated or enforced by a CLI process."
            )
            if not model:
                report["limitations"].append("The app selected the reviewer model; its actual model identifier was not recorded.")
            if len(replies) != len(parts):
                missing = sorted(set(range(1, len(parts) + 1)) - set(numbers))
                raise ValueError(f"Native review is incomplete; missing parts {missing}. "
                                 "Supplied valid concerns are retained, not a completed assessment.")
            report.update(status="reviewed",
                          response_sha256=digest(response_raw),
                          limitations=list(dict.fromkeys(report["limitations"])))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.TimeoutExpired, SystemExit) as exc:
        report["limitations"].append(f"Review unavailable: {exc}")
    if record_dir is None:
        root = run / "safeguard-reviews"
        root.mkdir(exist_ok=True)
        record_dir = Path(tempfile.mkdtemp(prefix="review-", dir=root))
        report["record_directory"] = str(record_dir.relative_to(run))
    # Keep the original preparation to explain exactly what the reviewer saw.
    filename = "review.json" if review_response is None else "final-review.json"
    (record_dir / filename).write_text(json.dumps(report, indent=2) + "\n")
    write_reports(run, report)
    return report


def review(run: Path, provider: str, model: str, timeout: float = 180,
           max_input_chars: int = 240000, prepare_only: bool = False,
           max_review_parts: int = 8) -> dict:
    # Programmatic callers must not silently launch a CLI for a native run.
    try:
        if json.loads((run / "run.json").read_text()).get("execution_mode") == "native":
            return native_review(run, provider, model, max_input_chars,
                                 max_review_parts=max_review_parts)
    except (OSError, ValueError, AttributeError):
        pass
    root = run / "safeguard-reviews"
    root.mkdir(exist_ok=True)
    record_dir = Path(tempfile.mkdtemp(prefix="review-", dir=root))
    packet: dict = {}
    report = {"schema_version": "ensemble-paper-audit.safeguard-review.v1",
              "status": "unavailable", "provider": provider, "model": model,
              "run_directory": str(run), "input_sha256": "", "reviewed_artifacts": [],
              "record_directory": str(record_dir.relative_to(run)),
              "summary": "Advisory review unavailable; human review is still needed.",
              "concerns": [], "limitations": []}
    try:
        packet, report["reviewed_artifacts"] = build_packet(run, provider)
        encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        (record_dir / "input.json").write_text(encoded)
        report["input_sha256"] = digest(encoded.encode())
        report["limitations"] = list(packet["limitations"])
        report["integrity_gate_exit_code"] = packet["integrity_gate"]["exit_code"]
        if packet["integrity_gate"]["exit_code"]:
            raise ValueError("The audited run failed its deterministic integrity gate; "
                             "an advisory cannot make that result valid. See input.json diagnostics.")
        parts, directories = prepare_parts(record_dir, packet, max_input_chars, max_review_parts, False)
        report["planned_parts"] = len(parts)
        report["reviewed_parts"] = 0
        report["parts_sha256"] = digest((record_dir / "parts.json").read_bytes())
        if prepare_only:
            raise ValueError("Preparation only: no model review was requested.")
        env = dict(os.environ)
        for name in ("CODEX_SESSION_ID", "CODEX_THREAD_ID", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "CODEX_CI", "CLAUDECODE"):
            env.pop(name, None)
        for index, (part, directory) in enumerate(zip(parts, directories), 1):
            prompt = (directory / "prompt.txt").read_text()
            with tempfile.TemporaryDirectory(prefix="paper-audit-safeguard-") as sandbox_raw:
                sandbox = Path(sandbox_raw)
                if provider == "codex":
                    from codex_adapter import ensure_codex_home
                    env["CODEX_HOME"] = str(ensure_codex_home(requested_home=sandbox / "runtime"))
                cmd = reviewer_command(provider, model, sandbox)
                (directory / "command.json").write_text(json.dumps(cmd, indent=2) + "\n")
                with (directory / "agent.stdout").open("w") as stdout, (directory / "agent.stderr").open("w") as stderr:
                    completed = subprocess.run(cmd, input=prompt, text=True, stdout=stdout,
                                               stderr=stderr, env=env, cwd=sandbox, timeout=timeout)
            if completed.returncode:
                raise ValueError(f"Reviewer part {index}/{len(parts)} exited with status {completed.returncode}: "
                                 f"{failure_detail(directory)} No automatic retry or model fallback was attempted.")
            response = parse_response((directory / "agent.stdout").read_text(), provider)
            (directory / "response.json").write_text(json.dumps(response, indent=2) + "\n")
            add_response(report, response, part, index, len(parts))
        for artifact in report["reviewed_artifacts"]:
            if digest((run / artifact["path"]).read_bytes()) != artifact["sha256"]:
                raise ValueError("Audited artifacts changed during review; advisory no longer matches them.")
        report.update(status="reviewed", limitations=list(dict.fromkeys(report["limitations"])))
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired, SystemExit) as exc:
        report["limitations"].append(f"Review unavailable: {exc}")
    (record_dir / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    write_reports(run, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--provider", choices=sorted(DEFAULT_MODELS),
                        help="reviewer provider (defaults to audited provider); audited transcript format still follows run.json")
    parser.add_argument("--model", help="reviewer model only; does not change verification models")
    parser.add_argument("--timeout", type=float, default=180, help="seconds for one reviewer invocation")
    parser.add_argument("--max-input-chars", type=int, default=240000)
    parser.add_argument("--max-review-parts", type=int, default=8,
                        help="maximum planned independent review packets; no retries")
    parser.add_argument("--prepare-only", action="store_true", help="capture packet without calling a model")
    parser.add_argument("--native", action="store_true", help="prepare an app-subagent review without a provider CLI (automatic for native runs)")
    parser.add_argument("--review-response", type=Path, help="ingest a native reviewer's JSON reply to the previously prepared packet")
    parser.add_argument("--reviewer-id", help="actual identifier of the fresh native reviewer subagent")
    args = parser.parse_args()
    run = args.run.expanduser().resolve()
    if not run.is_dir():
        parser.error("--run must be an existing completed run directory")
    if args.timeout <= 0 or args.max_input_chars <= 0 or args.max_review_parts <= 0:
        parser.error("--timeout, --max-input-chars and --max-review-parts must be positive")
    provider = args.provider
    if provider is None:
        try:
            provider = json.loads((run / "run.json").read_text())["provider"]
        except (OSError, ValueError, TypeError, KeyError):
            parser.error("could not infer provider from run.json; specify --provider")
    if provider not in DEFAULT_MODELS:
        parser.error("unknown run provider; specify --provider codex or claude")
    try:
        native_run = json.loads((run / "run.json").read_text()).get("execution_mode") == "native"
    except (OSError, ValueError, AttributeError):
        native_run = False
    if args.review_response is not None and args.prepare_only:
        parser.error("--review-response cannot be combined with --prepare-only")
    if args.reviewer_id and args.review_response is None:
        parser.error("--reviewer-id accompanies --review-response")
    if args.native or native_run:
        report = native_review(run, provider, args.model, args.max_input_chars,
                               args.review_response, args.reviewer_id, args.max_review_parts)
    else:
        if args.review_response is not None:
            parser.error("--review-response requires an app-native run")
        report = review(run, provider, args.model or DEFAULT_MODELS[provider], args.timeout,
                        args.max_input_chars, args.prepare_only, args.max_review_parts)
    print(f"Advisory {report['status']}: {len(report['concerns'])} concern(s). "
          f"See {run / 'safeguard-review.md'}. Do not automatically rerun the verifier.")
    if report.get("native_preparation_ready"):
        if report.get("planned_parts", 1) > 1:
            print(f"Give each part-*/prompt.txt under {run / report['record_directory']} "
                  "to a separate fresh app reviewer. Ingest the ordered response bundle "
                  "with --review-response PATH; see references/safeguard-review.md.")
        else:
            print(f"Give a fresh app reviewer the complete contents of {run / report['record_directory'] / 'prompt.txt'}. "
                  "Then ingest its JSON reply with --review-response PATH --reviewer-id ID.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
