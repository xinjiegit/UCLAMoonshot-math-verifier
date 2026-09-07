---
name: math-paper-verifier
description: Audit a mathematical paper with mutually blind verification passes and auditable external-source checks. Use when asked to verify, referee, stress-test, or check a math manuscript with Codex or Claude Code, including their desktop apps without a separately installed provider CLI. Accepts TeX, Markdown, text, PDF, or a TeX source directory; also supports focused, refuter, argument-spine, and citation passes.
metadata:
  version: "v.1.0"
---

# Math Verifier v.1.0

Structured verification for mathematical papers.

**Already a delegated worker?** If your task is a prepared native pass, region,
planner, reducer, or safeguard review, execute only that assigned task with its
supplied inputs. Do not restart the standard workflow, launch a provider CLI,
or read other passes' results because this skill was discovered automatically.
The parent coordinates the overall audit. Host safety and permission rules
still apply. The routing and workflow below are for the main coordinator.

Use one shared mathematical procedure with the execution path appropriate to
the user's environment. Independent passes must not receive one another's
findings. Native app workers and CLI processes offer different isolation and
recording capabilities; record the path actually used, not an assumed guarantee.

Read `references/audit-profiles.md` and `contract/pass-registry.json` completely
before selecting a workflow. The registry controls pass prompts and network
policy. Also read the selected execution reference below completely.

## Select execution

- **Codex app or Claude Code in the desktop app:** default to app-native
  subagents. Read `references/native-execution.md`. The Python helpers prepare
  and validate local files; they do not launch provider executables, read CLI
  credentials, or require a provider API key. An installed CLI does not change
  this default.
- **Terminal/automation, or an explicit request for the CLI runner:** read
  `references/cli-execution.md`. Use `run/run_codex.py` for Codex or
  `run/run_claude_code.py` for Claude Code. These require the corresponding
  authenticated CLI.
- A request for no CLI always selects native execution. If the host lacks a
  required capability (fresh subagents, local file tools, or permitted source
  retrieval), explain the missing capability. Do not install software, change
  host settings, silently switch runners, or simulate independent passes in
  the main conversation.

Both paths share mathematical prompts, schemas, preparation, and validators.
Verification workers inherit host model and reasoning settings unless the user
requests an override. The independent advisory reviewer may use a lightweight
model where supported; see `references/safeguard-review.md`.

Native execution uses the current app's provider; setting a metadata label does
not switch providers. For a different provider, explain that its app is needed
or obtain the user's choice to use that provider's CLI runner instead.

## Standard workflow

Unless the user requests particular passes only:

1. Run independent global and decomposed mathematical passes without web
   access. In native mode, use fresh app subagents and available host tool
   controls; absent controls, the boundary is an instruction, not an enforced
   sandbox.
2. Check input integrity and validate both outputs, then union findings by
   location and failure mechanism.
3. Inventory load-bearing external obligations in another fresh, web-disabled
   external-obligations pass.
4. Verify the validated inventory in a fresh web-enabled external-verification
   pass that receives the obligations, not the manuscript.

Announce bounded source retrieval and continue without a separate approval
pause, subject to host permissions. For an internal-only audit, stop after the
mathematical union and state that external claims were not checked.

Repository studies supply their own private protocols. This public skill does
not choose experiment arms, model settings, scoring rules, seals, or coordinator
approvals.

## Independent passes and validation

Read `references/finding-locations.md` before dispatching workers. Every finding
should include reader-facing section, statement, proof, and equation references
where established, alongside source lines and a precise quote. Never guess
compiled numbering. If the user supplies source and its compiled PDF, pass the
PDF as `--reference-pdf` to mathematical and inventory preparation; do not send
it to external-verification. Without a PDF, use supported source labels and
descriptive anchors rather than compiling the paper just to obtain locations.

Prepare each pass in a fresh directory from the submitted paper or allowlisted
TeX dependency closure. Keep answer keys, previous reviews, and other passes'
findings out of its handoff. Run concurrently when practical. The decomposed
pass retains regions of roughly four numbered equations; reduce concurrency
rather than coarsening the partition. Native hosts without nested delegation
use the flat region-worker procedure in `references/native-execution.md`.

Use `run/run_native.py finalize` for native runs and the matching provider gate
for CLI runs. Use the shared validators for ordinary output, external artifacts,
and argument-spine sidecars as detailed in the selected execution reference.

Do not use results with a known integrity failure, such as modified inputs or
observed web use in a designated blind pass. Missing native transcript export
is an audit limitation, not evidence of misconduct. Filename, mention, and
network-shaped command warnings are advisory. Repair JSON shape, ordering, or
numbering using the existing result and validator message; update linked IDs
and regenerate Markdown. Do not repeat mathematics for formatting alone or
give a repair worker another pass's findings.

## Advisory safeguard review

After each completed pass, read `references/safeguard-review.md` and use its
execution-specific review procedure. Native mode prepares a packet for a fresh
app subagent and imports its response locally; CLI mode launches a separate
process. Large packets are partitioned into a bounded set of fresh reviews,
with the complete input preserved; follow the same guide for native response
bundles. Do not use a CLI reviewer for native execution.

Reviews write `safeguard-review.json` and `safeguard-review.md`. Concerns and
missing evidence are for the human, not mathematical findings or retry triggers.
If review is unavailable, record the limitation and continue with valid results;
never label the run clean. Do not feed reviews back to blind workers.

## External obligations and sources

Create `blind-external-coverage.json` from the selected mathematical passes'
`coverage_notes.external_checks_not_performed` entries and output hashes.
Supply it to the inventory as `--coverage-input` and validate against it.
Supply the validated inventory as `--obligations` to external verification.
Do not include the manuscript, mathematical findings, or original manuscript
path in the source worker's staged inputs or delegation message.

Only registry-declared source-verification passes may retrieve outside sources.
Log each query and fetched URL. Preserve available host-observed activity
separately; never invent a transcript from the authored log. The reviewer
assesses both when available. There is no word allowlist or exact
transcript-to-log equality gate; search suggestions are starting points.

Inspect every `used:true` source before merging. It must be independent of the
manuscript, other versions or mirrors, associated repositories, derivative
pages, and citing restatements. If uncertain, use `unknown` and `undecidable`.
A failed search is not evidence that a theorem is false.

## Merge and report

Read `references/merge-protocol.md` completely. Match defects by location and
mathematical mechanism, never finding ID. Combine nonduplicative evidence and
retain every nonduplicate singleton. Express doubt through confidence and
unresolved checks. Sort by severity, assign fresh IDs, keep provenance in
`merge-map.json`, and validate the merged output.

Preserve supported reader-facing and source locations through the merge. The
Markdown renderer displays them separately and cannot reconstruct absent
locations from line numbers; add those to the JSON using the supplied paper
before rendering, without changing the mathematical finding.

Record input hashes, pass paths, provider, execution mode, worker identities,
network policy, optional passes, source-manifest details, and audit limitations
in `run.json`. Do not add provenance fields to the mathematical output schema.

Render the final report from its authoritative JSON:

```sh
python3 <skill-dir>/scripts/render_report.py <final-directory>/verifier-output.json \
  --safeguard-review <global-run>/safeguard-review.json \
  --safeguard-review <decomposed-run>/safeguard-review.json \
  --safeguard-review <inventory-run>/safeguard-review.json \
  --safeguard-review <external-run>/safeguard-review.json
```

Include one review path for every included run, including inventory and optional
passes; omit paths for passes not requested. Regenerate Markdown after JSON
changes. Lead with verdict and finding count. Link `verifier-report.md`,
`verifier-output.json`, `merge-map.json`, `run.json`, source artifacts, and
reviews. State unreviewed regions, unverified sources, and execution limitations.
`accept` means no reportable defect was found within the inspected material,
not that the theorem has been proved correct.

## Optional passes

Use fresh workers for requested `argument-spine`, `refuter`, `focused-sweep`
(`--focus` supplies the axis), or `citation` passes. An explicit `only`
request suppresses the standard workflow. Citation passes may use web access
and must produce a fetch log. Never execute submitted build files, TeX shell
escapes, or paper-supplied code without separate user authorization and review.

The sibling `math-paper-verifier-central-refuter` and
`math-paper-verifier-focused` skills are shortcuts for just one of these passes.
The focused shortcut takes a user-specified focus; equations and boundary cases
are examples, not an exhaustive menu. Follow `references/shortcut-execution.md`
when invoked through a shortcut. They reuse this skill's implementation and treat invocation as an
explicit single-pass request. For a single pass, render its validated output
directly; only create a merge map when results are actually merged.
