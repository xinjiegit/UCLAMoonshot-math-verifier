# Independent reconstruction of critical calculations

This native stage supplements the original mathematical passes. It checks selected
calculations whether or not a defect was proposed. It is also available alone when
the user requests reconstruction only. It does not replace a full paper audit or
establish theorem truth outside its actual coverage.

## Selection and input conditions

Use a fresh planner with the entire manuscript and the user's requested scope.
The planner traces dependencies to the main claims and selects computations whose
exact result enables a later inference. Give it neither previous findings nor a
known diagnosis. Keep prerequisites, convention definitions, and downstream use
together in a target. Do not hardcode particular papers, equation numbers, or
expected error types into the skill.

Respect user resource limits; record unselected critical targets as incomplete
coverage. Do not claim exhaustive selection merely because a requested count was
reached. Choose the count before reading mathematical results, not by retrying
until a desired defect appears. A user-selected target is a targeted diagnostic,
not unguided discovery.

The stage is offline. Explicitly supplied local references may be staged using
`--reference`; record their hashes and distinguish manuscript-only from reference-
assisted runs. Do not silently download a reference under a no-web instruction.
External-source retrieval, when authorized, remains a separate original pass.
Do not treat a source match as verification of the manuscript's construction.

The helper accepts one PDF or UTF-8 manuscript file, plus optional reference files.
It stages original PDFs together with page-delimited extracted text. Workers
should consult the original page when extraction makes a sign or notation unclear.
For a multi-file TeX project, first use the original input preparer to produce its
allowlisted source bundle; this helper does not follow includes or run builds.
Do not imply omitted files were available.

## Native execution

Use an existing Python 3.10+ interpreter; PDF input additionally needs pypdf.
Resolve `<skill>` relative to this skill's SKILL.md and use fresh run directories.
The helper stages files and validates artifacts only; it never launches a model.

```sh
python3 <skill>/run/reconstruction.py prepare-plan \
  --paper <manuscript> --out <run>/plan --scope '<requested scope>'
```

Optional references: repeat `--reference <local-file>` on this command.

Dispatch a fresh native subagent with only the resulting absolute
`worker-prompt.txt` path. Use `fork_turns="none"` when supported. Do not send this
conversation, repository notes, evaluation labels, prior reports, or an expected
answer. Record the exact handoff and actual worker identifier. The worker writes
`plan.json` under the reconstruction-plan.v1 contract.

For every selected target:

```sh
python3 <skill>/run/reconstruction.py prepare-pair \
  --plan-run <run>/plan --target-id T1 --out <run>/T1
```

Dispatch **two distinct fresh workers**, one to each of `T1/a/worker-prompt.txt`
and `T1/b/worker-prompt.txt`. They receive identical mathematical inputs, never
each other's results. Either may finish first; preserve both without feeding an
answer or suggested correction to the other. Reuse no context exposed to prior
target results for an independent derivation. Concurrency is optional; freshness
is required. Both write `result.json` in their own directories.

```sh
python3 <skill>/run/reconstruction.py check-pair --run <run>/T1
```

This checks unchanged inputs, target identity, required evidence fields, and links
to existing evidence. It reports candidate_supported, candidate_defect, disputed,
unresolved, or incomplete. These are structural summaries, not mathematical
verdicts. A missing worker cannot count as a supported pair. Repair formatting
from the same worker's existing reasoning without giving it the other result.
Do not repeat a mathematical attempt simply because the result was a miss.

Then prepare a fresh mathematical reconciliation using `prepare-review`:

```sh
python3 <skill>/run/reconstruction.py prepare-review \
  --run <run>/T1 --out <run>/T1-review
```

Dispatch a new worker with that directory's `worker-prompt.txt`. It receives the
raw materials and both completed derivations, but no other review or expected
answer. It checks model identification, conventions, calculations, and downstream
consequences. It must not infer correctness from agreement. The reviewer writes
`review.json`; validate its linkage and unchanged inputs with:

```sh
python3 <skill>/run/reconstruction.py check-review --run <run>/T1-review
```

Retain worker IDs, exact prompts, hashes, tools/model settings actually exposed,
and limitations in coordinator metadata outside staged input. Fresh contexts do
not enforce filesystem isolation or remove model prior knowledge. If the host
cannot disable network per worker, the offline boundary is an instruction. No
available activity export means conduct is unobserved, not certified clean. The
coordinator's authored metadata is not a provider transcript.

## What closes a target

A mathematical closure needs a concrete derivation, an explicit connection from
the computed model to the manuscript's construction, matching conventions, and
the independent reconciliation. A quotation, filled JSON fields, or agreement
alone is insufficient. The validator enforces necessary structural conditions;
the mathematical reviewer checks whether the evidence actually establishes them.

For orientation-sensitive work, the relevant evidence includes source and ambient
orientations, ordered bases, coordinate changes, and the sign-producing expression.
For other calculations use the corresponding definitions and intermediate steps.
Do not require irrelevant geometric fields or code execution for an analytic proof.
Exact scripts check arithmetic, not the choice of model. Numerical agreement needs
an error bound before it can establish an exact identity or sign.

Keep source_agreement, convention_match, and construction_match separate. A
resolved local outcome may coexist with an unknown downstream consequence; it
must not be discarded just because the theorem's ultimate truth is undecided.
An unresolved local computation is an explicit coverage limit, not an allegation.
Never infer a defect merely from missing web access or omitted routine exposition.

## Merge and reporting

Only mathematically reviewed defects enter the ordinary findings union. Use the
original output contract to classify their demonstrated effect; preserve the
precise location and evidence. Do not require theorem falsity or proven
irreparability to report an invalid proof step. Do not invent a repair or label
a defect unsalvageable solely because no repair was supplied.

Keep a separate target table linking selection, both derivations, validation, and
review. Preserve all unresolved, disputed, unselected, and unfinished critical
targets. A source-verification result cannot erase an unresolved application
calculation. A legacy `accept` with such targets must be presented as incomplete
verification with no established defect in the checked portion, not as a complete
validation of the proof. Do not manufacture a defect to avoid that distinction.

## Evaluating improvements

Freeze input hashes, prompts, model/effort, network condition, and resource budgets
before a comparison. Preserve detection, localized unresolved concern, false
allegation, and miss as different outcomes. Include independently checked correct
controls and errors held out from prompt design. Run repeated fresh trials under
matched conditions before making reliability claims. An answer-informed development
case is a regression diagnostic even if its individual workers have fresh contexts.
Historical audits with different budgets or inputs are descriptive context, not
a controlled baseline. Keep evaluation answer keys outside worker inputs.
