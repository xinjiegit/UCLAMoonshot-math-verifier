# App-native execution (no provider CLI)

Use the current app's subagent tools to run the verification, not shell commands
that start `codex`, `claude`, an SDK, or an API client. Python 3.10+ handles only
local preparation, validation, and reporting. PDF preparation additionally uses
`pypdf`; TeX and text require no extra Python package. Check the interpreter's
version: `python3` on some Macs is older than 3.10. Use an existing supported
interpreter, including an app-provided runtime when available, and substitute
its absolute path in the examples below. Do not install dependencies without
authorization.

This path targets local Codex app sessions and the **Code** surface in Claude's
desktop app, not an ordinary Claude Chat conversation. Both must expose fresh
subagents, local file tools, and (for source checks) permitted web retrieval.
The installed skill is sufficient; no custom agent installation, provider CLI
login, API key, or persistent host-settings changes are part of this procedure.

## Host capabilities and boundaries

- Use the subagent tool actually exposed by the host. In Codex, if it exposes
  `spawn_agent` with `fork_turns`, set `fork_turns="none"`. Other host versions
  may name this differently; select a fresh context without conversation
  history. Use subagents of the current task, not new user-owned app tasks.
- In Claude Code, use an available general-purpose Agent/Task subagent with a
  new context. Do not select the `fork` type or resume an agent from a different
  pass. Do not assume a tool name or optional parameter that is not exposed.
- Inherit the verification model/effort unless the user requests an override.
  Keep the worker handoff limited to its task and prepared inputs. Never fork
  parent discussion, previous reviews, known answers, or another pass's findings.
- Restrict web access for mathematical and inventory workers where the host
  offers per-worker controls. Otherwise give the no-web instruction and record
  that it is instruction-scoped. Do not modify account/project permissions or
  bypass a host restriction to implement this skill.
- Staged inputs and separate contexts reduce accidental leakage; they do not
  prevent arbitrary filesystem reads. Native subagents may inherit host rules,
  skills, memory, and permissions. Do not claim a skill-less process or complete
  tool capture. If known answer material is inherited, disclose the contamination
  and do not present that worker as blind.

If fresh subagents or local tools are unavailable, report the missing capability
instead of doing all passes in one context. If only web retrieval is unavailable,
retain valid internal results and report source verification as incomplete. Do
not repeatedly retry unavailable capabilities or silently invoke a CLI.

## Prepare and dispatch a pass

Resolve `<skill-dir>` and choose a fresh `<run>` directory outside the submitted
paper/source directory. Prepare each pass separately:

```sh
python3 <skill-dir>/run/run_native.py prepare --provider codex \
  --paper <paper-or-source-dir> --pass global --out <global-run>
python3 <skill-dir>/run/run_native.py prepare --provider codex \
  --paper <paper-or-source-dir> --pass decomposed --out <decomposed-run>
```

Use `--provider claude` in Claude Code. Pass `--root main.tex` when selecting a
root in a TeX directory and `--focus "..."` for a focused sweep. The helper
reuses the shared prompt and input preparer; it does not start a model. It
creates staged inputs, `worker-prompt.txt`, and coordinator metadata `run.json`.
The provider flag records the actual host; it cannot make a Codex app worker
run Claude or vice versa. Do not relabel workers to satisfy a cross-provider
request. Use the requested provider's app or ask about an explicit CLI path.

When the user also supplies the matching compiled PDF, add
`--reference-pdf <compiled.pdf>` to each source-based mathematical or inventory
preparation. It stages the PDF and page-aware text under `input/compiled/`;
it never compiles TeX or verifies a revision match automatically. Follow
`finding-locations.md` to match passages and record readable locations. Do not
pass this option to external-verification: that worker only receives locations
through the inventory. For PDF-only input, `--paper <paper.pdf>` is sufficient.

Dispatch each worker with only the absolute path to its `worker-prompt.txt`
and the instruction to read and execute that one task. The prepared prompt
specifies input and output locations and how the shared prompt's relative
paths/JSON output map to the app. Do not give workers the repository path,
parent conversation, another run directory, or coordinator metadata. Do not
invoke the whole skill recursively inside each worker.

If the host only returns text, preserve its exact JSON as the requested artifact
using file tools; do not replace it with your summary. If a worker writes files,
wait for completion before validation. Retain its actual host worker ID. Known
partial work remains partial even if its JSON parses.

Save the exact task messages and worker IDs in `native-workers.json`, for example:

```json
{
  "schema_version": "native-workers.v1",
  "workers": [
    {
      "worker_id": "HOST_ID",
      "role": "global",
      "prompt": "worker-prompt.txt",
      "task_message": "The exact task message sent to this worker."
    }
  ]
}
```

This is coordinator-authored provenance, not a captured activity transcript.
Record actual host model/tool controls when known; use unknown rather than
inventing them. Do not edit preparation hashes or claim a stronger boundary than
was available.

## Decomposition when nested workers are unavailable

When the decomposed worker can delegate, it follows the shared decomposed
prompt and records its region assignments. Every nested worker also starts
without inherited conversation history (including `fork_turns="none"` when
exposed) and receives only its assigned task and staged inputs. When it cannot
delegate with that boundary, the main app
coordinator schedules the same work as sibling subagents:

1. Start a fresh planning worker with the decomposed task, explicitly scoped
   to its partitioning stage only. Request region IDs and precise spans, not
   a final mathematical report. Keep approximately four numbered equations per
   region; include proof/prose regions as appropriate.
2. Save the plan in `decomposition-ledger.json`. For each region, dispatch a
   fresh worker with the shared decomposed prompt's **region-worker** instructions,
   the appended reader-facing location guidance, its assigned span, and access to that pass's complete staged manuscript for
   definitions and dependencies. It reports local problems and the span actually
   checked, not severity. Do not send global findings or other region reports.
3. Track assigned worker IDs, task-message paths, result paths, actual checked
   spans, and completion status in the ledger. Respect host concurrency; a small
   worker pool may be reused within this pass, but not across independent passes.
   Fill genuinely unreviewed tails or mark them unreviewed; do not coarsen the plan.
4. Start a fresh reducer with the shared decomposed prompt's consolidation
   instructions, staged manuscript, ledger, and region reports. It classifies
   and combines the region findings into `verifier-output.json`, checks global
   compatibility, and retains incomplete coverage. It receives no global-pass
   output. The main app only schedules this work and saves artifacts.

Save each exact planning/region/reduction handoff and returned report. Include
the handoff text in each `native-workers.json` entry's `task_message` so it is
available in the advisory packet, not just an unreadable file-path reference.
Add all participating IDs and roles; use the final reducer's
ID with `finalize`. The ledger is for human/advisory review, not an automated
semantic test of every partition choice. The same small-region procedure applies
to both providers; nested delegation is not a prerequisite for using the skill.

## Focused sweeps without nested workers

The same coordinator-managed pattern applies to `focused-sweep`, including the
equation and boundary aliases. If the worker cannot delegate to fresh contexts:

1. Give a fresh planner the prepared focused-sweep prompt, limited to its
   checklist-enumeration and partitioning stages. It lists all applicable items
   in the requested scope and assigns coherent blocks, not mathematical verdicts.
2. Save the checklist and block assignments in `decomposition-ledger.json`,
   labeled as focused-sweep checklist blocks. Start fresh sibling workers with
   the prepared task restricted to their assigned items (no further delegation),
   its location guidance, and the staged paper for definitions and dependencies.
   Each records item-level CONFIRMED, MISMATCH, or CANNOT-DERIVE results and
   supporting derivations. Workers do not receive other blocks' findings.
3. Give a fresh reducer the staged paper, focused-sweep instructions, checklist,
   and block results. It builds one `verifier-output.json`, preserving every
   item and verdict in `coverage_notes.reviewed_regions` and explicitly marking
   incomplete blocks. It must not broaden the mathematical scope.

Keep this as one mathematical pass, not a global/decomposed review. Save the
exact handoffs, output paths, worker IDs, and completion states using the same
`native-workers.json` and ledger conventions above. Finalize with the reducer's
ID and review the complete recorded run. The ledger remains provenance for
human/advisory review, not a new deterministic coverage gate.

## Finalize and record evidence

```sh
python3 <skill-dir>/run/run_native.py finalize --run <run> --worker-id <host-id>
```

This checks unchanged prepared inputs and shared output contracts, including
sidecars and linked external artifacts. It is not a CLI transcript gate and
does not certify that every unobserved action obeyed the prompt. Fix formatting
from the existing result and finalize again; do not rerun mathematics for a
schema-only error. Do not edit native metadata to make a failed check pass.

When the app exposes an export of this worker's activity, preserve it with
`--transcript <export-path>`. Include nested worker activity when actually
available; label incomplete exports as partial. Never substitute an authored
fetch log, summary, or reconstructed events for a host transcript. If no export
is accessible, omit it; the report retains that limitation. Do not scan unrelated
session logs to find one. Observed boundary violations must still be disclosed
and affected results must not be merged as valid blind results.

If a worker launch reports a capacity limit, first let this audit's active
workers finish or reduce concurrency. If fresh workers remain unavailable with
no active work to wait for, record the exact failure and stop the affected pass.
Do not retry indefinitely, reuse a worker exposed to another pass, or manufacture
a completed report from preparation artifacts alone.

Follow each pass with the **native** advisory review in `safeguard-review.md`.
Do not run `audit_codex_run.py` or `audit_claude_run.py` against native artifacts;
those expect CLI event formats and process metadata.

## Inventory and external verification

After the mathematical passes, construct the shared narrow coverage handoff as
described in `SKILL.md`, then prepare and dispatch a new inventory worker:

```sh
python3 <skill-dir>/run/run_native.py prepare --provider codex \
  --paper <paper> --pass external-obligations \
  --coverage-input <coverage.json> --out <inventory-run>
```

Finalize and review the inventory before preparing the source worker:

```sh
python3 <skill-dir>/run/run_native.py prepare --provider codex \
  --paper <paper> --pass external-verification \
  --obligations <inventory-run>/external-obligations.json \
  --coverage-input <coverage.json> --out <external-run>
```

The coordinator's `--paper` argument is for provenance/preparation; it is not a
worker handoff. The source worker receives only its prepared prompt, obligations,
and contracts. Coverage input is retained for validation, not as access to blind
findings. Omit `--coverage-input` only when the inventory was made without it.

Use a new context with the app's available search/fetch tools. Keep source
retrieval within the skill's policy, record queries/URLs and source resolutions,
and distinguish unknown/unavailable evidence from a mathematical refutation.
Finalize and review this pass. Merge validated findings and render the same
JSON/Markdown report as CLI execution; include the native run limitations.

## Provider documentation

- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
  describes delegation within an app session.
- [Claude Code desktop](https://code.claude.com/docs/en/desktop-quickstart)
  includes the Code runtime without a separate CLI installation.
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents) describes
  fresh contexts, inherited configuration, and host-dependent delegation controls.

Use these to troubleshoot capability differences, not to assume an installed
version exposes every documented tool.
