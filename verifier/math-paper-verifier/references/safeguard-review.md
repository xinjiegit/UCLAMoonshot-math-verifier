# Advisory safeguard review

Review each completed pass with fresh independent reviewers, not another
mathematical verification pass. It receives that run's available activity
evidence, source obligations, authored fetch log, resolutions, and integrity
diagnostics. It does not load other passes' findings or retrieve new sources.
No review is fed back to a blind mathematical pass.

## Native app review (no provider CLI)

After `run/run_native.py finalize` succeeds, prepare the review locally:

```sh
python3 <skill-dir>/run/run_safeguard_review.py --run <completed-run> --native
```

This writes a preserved packet and `prompt.txt` under the reported
`safeguard-reviews/review-*/` directory. The root advisory remains **unavailable**
until a reviewer responds. Native run metadata also selects this mode when
`--native` is omitted, preventing an accidental CLI launch.

Read the generated prompt and supply its complete contents as the task message
to a **fresh app subagent** without parent history. Do not send only a file path:
the reviewer is instructed to use no tools, including file reads. Give it no
other pass's findings. Use a different agent from every verification, planning,
region, or reduction worker recorded for the pass. Disable its tools where the
host supports this; otherwise record that the no-tool boundary is instructional.
Do not change persistent host settings.

If the host exposes an independently selectable lightweight model, prefer it
for this review (for example a supported Codex lightweight model or Claude
Haiku). Do not override verification-worker models. If native model selection
is unavailable, use the app-selected reviewer and disclose that; do not claim
a lightweight model was used or invoke a CLI to obtain one.

Save the reviewer's exact JSON response outside the audited artifacts, then:

```sh
python3 <skill-dir>/run/run_safeguard_review.py --run <completed-run> --native \
  --review-response <reviewer-response.json> --reviewer-id <actual-host-id>
```

Optionally add `--model <actual-reviewer-model>` to **record** a known native
model choice; this does not select or launch a model. The helper validates the
response and binds it to the preserved packet and unchanged artifacts. A known
worker ID cannot also be its reviewer ID, but identity and fresh-context claims
remain coordinator-recorded, not independently authenticated.

The native packet preserves a supplied host activity export verbatim when one
is available. It does not fabricate events from authored logs. Missing or
partial capture, inherited configuration, and instruction-scoped restrictions
remain limitations even when `concerns:[]`. The reviewer can still flag a
suspicious query recorded in an authored log without a machine transcript.

One independent review is used when the packet fits. Large packets use the
bounded partition procedure below. Do not automatically re-dispatch after
a timeout, unsupported model, or unavailable tool. Leave the explicit
unavailable advisory and continue with valid mathematical results. A packet
that cannot be transferred intact should remain unavailable, not be silently
summarized. These limitations appear in the Markdown report.

### Large native packets

When preparation reports more than one part, `parts.json` lists the planned
parts and their hashes. The original full `input.json` remains intact. Give
each `part-001/prompt.txt`, `part-002/prompt.txt`, etc. to a **different fresh
app subagent**, with the same no-tool instructions above. The root `prompt.txt`
is only an index, not a review task. Do not pass one reviewer's answer to another.

Save the exact responses in one JSON bundle, in part order:

```json
{"reviews": [
  {"part": 1, "reviewer_id": "ACTUAL_HOST_ID_1", "response": {"summary": "...", "concerns": [], "limitations": []}},
  {"part": 2, "reviewer_id": "ACTUAL_HOST_ID_2", "response": {"summary": "...", "concerns": [], "limitations": []}}
]}
```

Import it with `--native --review-response <bundle.json>`; each entry supplies
its reviewer ID, so omit the single-review `--reviewer-id` option. Every prepared
part must have one response. Missing parts, reused reviewer IDs, modified packets,
or changed audited artifacts leave the review unavailable. A bundle missing parts
still preserves supplied valid concerns and reports the completed-part count;
it is not a completed assessment. Keep partial responses for human inspection;
do not manufacture replies for missing parts.

## CLI process review

For a CLI run, use `run/run_safeguard_review.py --run <completed-run>`. This
launches a separate process. Provider tools are disabled or restricted; Codex
also runs in a read-only sandbox with a private configuration.

The default lightweight models are `gpt-5.6-luna` for Codex and `haiku` for Claude
Code. Use `--model <model>` to change only the reviewer. Provider authentication
is reused; no separate API key or hosted service is required. A missing model
or failed command produces an explicit unavailable advisory, not a fallback to
another model or a repeated verification. These defaults can change with
provider availability; see the [Codex model documentation](https://learn.chatgpt.com/docs/models)
and [Claude model aliases](https://code.claude.com/docs/en/model-config).

## Separate integrity from judgment

Deterministic checks still require parseable artifacts, valid fields and IDs,
consistent links, unchanged inputs, and intact recorded evidence. CLI runs
require their captured transcripts; native export availability is a disclosed
limitation. Observed web-tool use in a web-disabled pass remains a boundary
failure. Syntax/order repairs need not repeat the mathematics.

Search relevance, natural query refinements, source independence, and apparent
contamination are judgments. Do not enumerate all permissible words or infer a
breach merely from a filename or URL in a command. The reviewer considers benign
explanations and flags concrete concerns with evidence for a human. It cannot
certify source independence from labels alone or override an integrity failure.

## Outputs and stopping

- `safeguard-review.json` records `reviewed` or `unavailable`, the selected model,
  concerns, limitations, and input hashes.
- `safeguard-review.md` renders the advisory for the human.
- `safeguard-reviews/review-*/` retains the input packet, prompt, provider output,
  and per-attempt report. The top-level report represents the latest invocation.

The default per-packet budget is 240,000 characters. A larger packet is split
into at most eight planned parts (`--max-review-parts`), each reviewed in a fresh
context. This is one partitioned assessment, not repeated attempts at the same
review. Compact source documents are repeated for context when they fit; larger
documents and individual oversized records are preserved in labeled fragments
with offsets and hashes. No tool-input characters are dropped. The full input
packet and original transcript remain available. Long tool **outputs** may still
have explicitly labeled excerpts, as recorded in the packet's limitations.

CLI review allows at most 180 seconds **per part** by default (at most 24 minutes
for eight parts); provider reconnections may occur inside that limit. It stops
on the first failed part, retains completed parts' concerns, and marks the overall
advisory unavailable. No orchestration retry or model fallback occurs. Native
review uses the same partition limits without launching a CLI. A packet that
cannot fit within the planned bounds remains unavailable before dispatch.

All parts must complete for status `reviewed`. Concerns are combined without
discarding a concern because another reviewer missed it. Independent parts cannot
necessarily assess relationships spanning packets; this remains a limitation,
not a claim that cross-packet consistency was checked. `--timeout`,
`--max-input-chars`, and `--max-review-parts` may be adjusted for an explicitly
requested follow-up. `--prepare-only` captures the complete plan without model calls.

The command exits successfully when an advisory (including unavailable) was
recorded. That exit is NOT approval of the underlying verification run. Always
run the selected execution path's integrity checks and output validators separately. A concern, timeout,
missing model, or unsupported reviewer output never triggers a verifier rerun.
Uncertainty, unavailable reviews, and missing source content must remain visible.

Append reviews with `scripts/render_report.py ... --safeguard-review <path>`
(repeat for each run included in a merged report). Keep advisories outside the
mathematical finding list and JSON verdict.
