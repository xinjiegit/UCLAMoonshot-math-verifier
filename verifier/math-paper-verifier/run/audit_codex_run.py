#!/usr/bin/env python3
"""Check run integrity and surface possible contamination for advisory review.

    ./run/audit_codex_run.py outputs/<run> [outputs/<run> ...]

Exit code 1 indicates an integrity failure or actual web-tool use in a blind
pass. Exit code 0 does not certify an uncontaminated run. Path keywords and
mentions are ambiguous signals for the advisory model and human, never proof
of an inappropriate read and never a reason to rerun automatically.

In --citation-mode, the machine-observed searches and direct URL lookups are
printed beside the model-authored citation-fetch-log.json for human review.
They are deliberately not required to correspond exactly: Codex event formats
vary by version. Search appropriateness and source independence require model
and human judgment; schema and cross-artifact consistency remain deterministic.
"""

from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Historical benchmark path hints, not a universal forbidden-path policy.
FORBIDDEN = [
    ("hidden_gold", "THE GOLD -- the answers themselves"),
    ("gold_annotation", "human-adjudicated gold"),
    ("paper_history", "erratum record (admitted_errors)"),
    ("comparisons/", "scored reports -- contain full erratum tables"),
    ("experiments/", "experiment specs -- quote admitted errors verbatim"),
    ("outputs/", "other arms' findings on the same paper"),
    ("HANDOFF.md", "describes the seed items and their errata"),
    ("score-verifier-run", "the grader skill"),
    ("SKILL.md", "ambient skill instructions outside the isolated workflow"),
    ("verifier_skills", "another verifier skill bundle"),
]

# Commands that OPEN a file, vs merely name it.
READERS = r"\b(cat|head|tail|sed|nl|awk|less|more|jq|rg|grep|python3?|open|wc)\b"


def strip_negated_globs(command: str) -> str:
    """Mask shell glob exclusions so their names are not treated as reads.

    Codex commonly uses ``rg --files -g '!**/SKILL.md'`` to keep forbidden
    files out of a listing.  The old substring check inverted that safeguard
    and classified the exclusion itself as a read of the excluded file.
    """
    probe = command
    for token, _ in FORBIDDEN:
        escaped = re.escape(token)
        probe = re.sub(
            rf"!\*+(?:/\*+)*{('/?' if not token.startswith('/') else '')}{escaped}",
            "«NEGATED_GLOB»",
            probe,
        )
    return probe

# Forbidden material can reach the model two ways: it runs a command naming it,
# OR a command's OUTPUT contains it (the item_seed_005 near-miss: `find` listed 19
# prior verifier-output.json paths). Scanning commands alone misses the second,
# so these patterns are matched against the whole transcript.
EXPOSURE = [
    (r"seed_data/hidden_gold\S*", "THE GOLD appeared in the transcript"),
    (r"\./?outputs/\S*verifier-output\S*", "another run's findings path appeared"),
    (r"\./?comparisons/\S+\.md", "a scored report path appeared"),
    (r"\./?experiments/E\d\S*\.md", "an experiment spec path appeared"),
    (r"admitted_errors|paper_history\.json", "erratum record named"),
]

FETCH_LOG_FIELDS = {
    "kind",
    "obligation_id",
    "query",
    "url",
    "used",
    "relationship_to_manuscript",
    "reason",
}
def legacy_transcript_web_queries(raw: str) -> set[str]:
    """Best-effort query extraction for pre-JSONL legacy runs only."""
    observed = {
        match.strip().strip('"\'')
        for match in re.findall(r"(?im)^\s*web query:\s*([^\r\n]+)", raw)
        if match.strip()
    }
    for match in re.findall(r'"(?:q|query)"\s*:\s*"((?:\\.|[^"\\])*)"', raw):
        try:
            value = json.loads(f'"{match}"')
        except Exception:
            value = match
        if value.strip():
            observed.add(value.strip())
    return observed


def structured_events(raw: str) -> list[dict] | None:
    """Parse a complete Codex exec JSONL stream, failing closed on mixed text."""
    events: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            return None
        events.append(event)
    return events or None


def structured_web_items(events: list[dict]) -> list[dict]:
    """Keep the latest machine event for each recognized web tool call."""
    items: dict[str, dict] = {}
    for event in events:
        if event.get("type") not in {"item.started", "item.completed"}:
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).lower()
        if "web_search" not in item_type:
            continue
        item_id = str(item.get("id", f"anonymous-{len(items) + 1}"))
        items[item_id] = item
    return list(items.values())


def structured_web_provenance(events: list[dict]) -> tuple[int, set[str], set[str]]:
    """Return recognized web items plus best-effort searches and direct URLs.

    Extraction is a display aid, not proof of complete network activity. The
    original events remain available to the advisory reviewer and human.
    """
    items = structured_web_items(events)
    queries: set[str] = set()
    urls: set[str] = set()

    def record(value: object, *, queries_allowed: bool) -> None:
        values = value if isinstance(value, list) else [value]
        for candidate in values:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            normalized = candidate.strip()
            if re.match(r"^https?://", normalized):
                urls.add(normalized)
            elif queries_allowed:
                queries.add(normalized)

    for item in items:
        action = item.get("action")
        if isinstance(action, dict) and action.get("type") == "search":
            if "queries" in action:
                record(action.get("queries"), queries_allowed=True)
            elif "query" in action:
                record(action.get("query"), queries_allowed=True)
            else:
                record(item.get("query"), queries_allowed=True)
        else:
            # Codex currently emits direct URL lookups and find/click labels
            # alike as action.type=other. Only the former are provenance.
            record(item.get("query"), queries_allowed=False)
        record(item.get("url"), queries_allowed=False)
        record(item.get("urls"), queries_allowed=False)
        if isinstance(action, dict):
            record(action.get("url"), queries_allowed=False)
            record(action.get("urls"), queries_allowed=False)
    return len(items), queries, urls


def transcript_web_queries(raw: str) -> set[str]:
    """Compatibility helper used by older callers and tests."""
    events = structured_events(raw)
    if events is not None:
        return structured_web_provenance(events)[1]
    return legacy_transcript_web_queries(raw)


def external_fetch_log_problems(run: Path, entries: list[dict]) -> list[str]:
    """Check log structure and references, not semantic search permissibility."""
    problems: list[str] = []
    obligation_path = run / "external-obligations.json"
    if not obligation_path.is_file():
        return ["external-source log has no sealed external-obligations.json"]
    try:
        obligation_data = json.loads(obligation_path.read_text())
        obligations = {
            item["obligation_id"]: item
            for item in obligation_data.get("obligations", [])
        }
    except Exception as exc:
        return [f"could not parse external-obligations.json: {exc}"]

    logged_used: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"fetch log entry {index + 1}"
        if not isinstance(entry, dict):
            problems.append(f"{label} is not an object")
            continue
        missing = FETCH_LOG_FIELDS - entry.keys()
        if missing:
            problems.append(f"{label} is missing {sorted(missing)}")
            continue
        extra = entry.keys() - FETCH_LOG_FIELDS
        if extra:
            problems.append(f"{label} has unexpected fields {sorted(extra)}")
        obligation_id = entry.get("obligation_id")
        if not isinstance(obligation_id, str):
            problems.append(f"{label} has non-string obligation_id")
            continue
        obligation = obligations.get(obligation_id)
        if obligation is None:
            problems.append(f"{label} names unknown obligation {obligation_id!r}")
            continue
        kind = entry.get("kind")
        query = entry.get("query")
        url = entry.get("url")
        if kind not in ("search", "fetch"):
            problems.append(f"{label} has invalid kind {kind!r}")
        if not isinstance(entry.get("used"), bool):
            problems.append(f"{label} has non-boolean used")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            problems.append(f"{label} has no reason")
        if entry.get("relationship_to_manuscript") not in (
            "independent", "same_manuscript", "derivative", "cites_manuscript", "unknown"
        ):
            problems.append(f"{label} has an invalid manuscript relationship")
        if kind == "search":
            if not isinstance(query, str) or not query.strip():
                problems.append(f"{label} search has no query")
            if url is not None:
                problems.append(f"{label} search must have url:null")
            if entry.get("used") is not False:
                problems.append(f"{label} search must have used:false")
            if entry.get("relationship_to_manuscript") != "unknown":
                problems.append(f"{label} search must have unknown relationship")
        elif kind == "fetch":
            if query is not None:
                problems.append(f"{label} fetch must have query:null")
            if not isinstance(url, str) or not re.match(r"^https?://", url):
                problems.append(f"{label} fetch has no HTTP(S) URL")
        if kind == "fetch" and entry.get("used") is True and isinstance(url, str):
            logged_used.add(url)

    verification_path = run / "external-verification.json"
    if not verification_path.is_file():
        problems.append("external-source log has no external-verification.json")
        return problems
    try:
        verification = json.loads(verification_path.read_text())
        artifact_used = {
            source["url"]
            for resolution in verification.get("resolutions", [])
            for source in resolution.get("sources", [])
            if source.get("used") is True
        }
    except Exception as exc:
        problems.append(f"could not parse external-verification.json: {exc}")
        return problems
    if logged_used != artifact_used:
        problems.append(
            "used source URLs in citation-fetch-log.json do not match "
            "external-verification.json"
        )
    return problems


def commands(text: str, events: list[dict] | None = None) -> list[str]:
    """Every shell command codex executed, de-ANSI'd."""
    if events is not None:
        observed: list[str] = []
        for event in events:
            if event.get("type") != "item.completed":
                continue
            item = event.get("item")
            if (
                isinstance(item, dict)
                and item.get("type") == "command_execution"
                and isinstance(item.get("command"), str)
            ):
                observed.append(item["command"])
        return observed
    text = ANSI.sub("", text)
    shell = r"/bin/(?:ba|z)?sh\s+-lc"
    double = [m.group(1) for m in re.finditer(shell + r'\s+"(.*?)"\s+in\s', text, re.S)]
    single = [m.group(1) for m in re.finditer(shell + r"\s+'(.*?)'\s+in\s", text, re.S)]
    return double or single


def audit(run: Path, citation_mode: bool = False) -> int:
    log = run / "ultra.stdout"
    if not log.exists():
        cands = list(run.glob("*.stdout"))
        if not cands:
            print(f"{run.name}: no *.stdout to audit"); return 1
        log = cands[0]
    raw = ANSI.sub("", log.read_text(errors="replace"))
    events = structured_events(raw)
    metadata_path = run / "run.json"
    metadata: dict = {}
    metadata_problem = None
    structured_required = False
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text())
            if not isinstance(metadata, dict):
                raise ValueError("run.json is not an object")
            structured_required = metadata.get(
                "event_stream_format"
            ) == "codex_exec_jsonl_v1"
        except Exception as exc:
            metadata = {}
            metadata_problem = str(exc)
            structured_required = True
    cmds = commands(raw, events)

    breaches, near = [], []
    for cmd in cmds:
        # A run legitimately reads and writes its OWN directory: the fan-out
        # orchestrator collects its regions/*.json and validates its own result.
        # Strip self-references before looking for forbidden paths, or every
        # manual fan-out run reports a false breach.
        probe = strip_negated_globs(
            cmd.replace(str(run), "«SELF»")
               .replace(f"outputs/{run.name}", "«SELF»")
               .replace(run.name, "«SELF»")
        )
        for token, why in FORBIDDEN:
            if token in probe:
                (breaches if re.search(READERS, probe) and not probe.strip().startswith("find")
                 else near).append((token, why, cmd[:160]))

    # Second channel: forbidden material surfaced in command OUTPUT, not the command.
    exposures = []
    for pat, why in EXPOSURE:
        hits = set(re.findall(pat, raw))
        # Ignore the run's own directory: it names itself legitimately.
        hits = {h for h in hits if run.name not in h}
        if hits:
            exposures.append((why, sorted(hits)[:6], len(hits)))

    if events is not None:
        web, observed_web_queries, observed_web_urls = structured_web_provenance(events)
    else:
        observed_web_queries = legacy_transcript_web_queries(raw)
        observed_web_urls = set()
        # Legacy logs are retained for old experiments, but are not a strong
        # provenance boundary and cannot satisfy a newly structured run.
        web = max(raw.count("web_search_end"), len(observed_web_queries))

    print(f"\n{'='*74}\nRUN {run.name}   ({len(cmds)} shell command(s))")
    status = 0
    if metadata_problem:
        status = 1
        print(f"  !! INTEGRITY -- could not parse run.json: {metadata_problem}")
    if not raw.strip():
        status = 1
        print("  !! EVENT_STREAM -- transcript is empty")
    if "codex_exit" in metadata and metadata["codex_exit"] != 0:
        status = 1
        print(f"  !! INTEGRITY -- Codex process exit was {metadata['codex_exit']!r}, not 0")
    if "sandbox_input_integrity" in metadata and metadata["sandbox_input_integrity"] is not True:
        status = 1
        print("  !! INTEGRITY -- prepared sandbox inputs were missing or changed")
    if events is None and (structured_required or raw.lstrip().startswith(("{", "["))):
        status = 1
        print("  !! EVENT_STREAM -- expected Codex JSONL is missing, mixed "
              "with text, or malformed")
    if structured_required or "event_stream_sha256" in metadata:
        observed_stream_sha = hashlib.sha256(log.read_bytes()).hexdigest()
        if metadata.get("event_stream_sha256") != observed_stream_sha:
            status = 1
            print("  !! EVENT_STREAM -- transcript hash does not match run.json")
    if events is not None and any(event.get("type") == "turn.failed" for event in events):
        status = 1
        print("  !! INTEGRITY -- provider transcript records a failed turn")
    if exposures:
        print("  ~  ADVISORY / EXPOSURE -- sensitive-looking text appeared in the "
              "transcript; a path mention is not evidence of reading its contents:")
        for why, sample, n in exposures:
            print(f"     {why}  ({n} occurrence(s))")
            for s in sample:
                print(f"       {s}")
    if breaches:
        print(f"  ~  ADVISORY / PATH READ -- {len(breaches)} command(s) combine "
              "a reader with a sensitive-looking path; review actual access and context:")
        for token, why, cmd in breaches:
            print(f"     [{token}] {why}\n       $ {cmd}")
    if near:
        print(f"  ~  ADVISORY / PATH MENTION -- {len(near)} command(s) name "
              "sensitive-looking paths:")
        for token, why, cmd in near:
            print(f"     [{token}] {why}\n       $ {cmd}")
    if web and not citation_mode:
        if events is not None:
            status = 1
            print(f"  !! WEB_SEARCH -- {web} machine-recorded web call(s) in a blind pass")
        else:
            print(f"  ~  ADVISORY / LEGACY WEB -- {web} possible web call(s); "
                  "legacy text cannot establish machine tool use")
    if events is None and raw.strip() and not structured_required:
        print("  ~  ADVISORY / LEGACY TRANSCRIPT -- web and file activity extraction "
              "is incomplete; review the original record")
    if not web:
        print("  ~  ADVISORY / OBSERVABILITY -- no recognized web calls extracted; "
              "this does not prove there was no network activity")
    if citation_mode:
        # Citation mode: web use is expected but must be bibliography-only.
        # Keep the provider transcript and authored fetch log visible together
        # for human comparison. Do not make exact correspondence a gate: the
        # structured shape of web events varies across Codex versions.
        log = run / "citation-fetch-log.json"
        entries = []
        log_problem = None
        if log.exists():
            try:
                parsed = json.loads(log.read_text())
                if isinstance(parsed, list):
                    entries = parsed
                    if any(not isinstance(entry, dict) for entry in entries):
                        log_problem = "citation-fetch-log.json entries must be objects"
                else:
                    log_problem = "citation-fetch-log.json is not a JSON array"
            except Exception as exc:
                log_problem = f"could not parse citation-fetch-log.json: {exc}"
        print(f"  ~  CITATION MODE: {web} web call(s); fetch log has {len(entries)} entr(y/ies)")
        structured_external_mode = (run / "external-obligations.json").is_file() or any(
            "obligation_id" in entry or "relationship_to_manuscript" in entry
            for entry in entries
            if isinstance(entry, dict)
        )
        if not log.exists():
            status = 1
            print("  !! no citation-fetch-log.json — source retrieval is not auditable")
        elif log_problem:
            status = 1
            print(f"  !! {log_problem}")
        bad = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("used")
            and (
                str(entry.get("reason", "")).strip().lower().startswith("describes paper")
                or (
                    structured_external_mode
                    and entry.get("relationship_to_manuscript") != "independent"
                )
            )
        ]
        if bad:
            print(
                f"  ~  ADVISORY / SOURCE RELATIONSHIP -- {len(bad)} used log entr(y/ies) "
                "are labelled non-independent or describe the manuscript; review "
                "source appropriateness, not just the model's label"
            )
        if structured_external_mode:
            fetch_problems = external_fetch_log_problems(run, entries)
            if fetch_problems:
                status = 1
                print("  !! external-source artifact integrity failed:")
                for problem in fetch_problems:
                    print(f"     - {problem}")
        print("  ~  MACHINE-OBSERVED WEB ACTIVITY (provider transcript):")
        if events is not None:
            for item in structured_web_items(events):
                print(f"     tool event: {json.dumps(item, ensure_ascii=False, sort_keys=True)}")
        if observed_web_queries:
            for query in sorted(observed_web_queries):
                print(f"     search: {query}")
        else:
            print("     search: (none extracted)")
        if observed_web_urls:
            for url in sorted(observed_web_urls):
                print(f"     fetch:  {url}")
        else:
            print("     fetch:  (none extracted)")
        print("  ~  MODEL-AUTHORED FETCH LOG:")
        if entries:
            for entry in entries:
                print(f"     {json.dumps(entry, ensure_ascii=False, sort_keys=True)}")
        else:
            print("     (no entries)")
        print(
            "  ~  ADVISORY / HUMAN REVIEW: examine actual queries, source relationships, "
            "and the authored fetch log. No word allowlist or exact correspondence "
            "is enforced; suspicious activity is a review flag, not an automatic retry."
        )
    if not status:
        print("  INTEGRITY CHECKS PASSED -- advisory review remains separate; "
              "this is not a certification of appropriate activity")

    outside = [c for c in cmds if "/verifier_human_loop" in c]
    if outside:
        print(f"  note: {len(outside)} command(s) reference the repo by absolute path")
    return status


def main() -> int:
    args = sys.argv[1:]
    citation_mode = "--citation-mode" in args
    runs = [Path(a) for a in args if a != "--citation-mode"]
    if not runs:
        raise SystemExit(__doc__)
    worst = 0
    for r in runs:
        worst |= audit(r, citation_mode)
    print(f"\n{'='*74}\n{'INTEGRITY OR ISOLATION CHECK FAILED' if worst else 'INTEGRITY CHECKS PASSED; REVIEW ADVISORIES'}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
