# Central refutation with original reconstruction

Combine the original central-claim refuter with independent reconstruction of critical calculations. This is the default for the central-refuter shortcut and central-refutation requests. Both derivation workers use the same reconstruction procedure; do not replace one with a general refutation strategy.

## Scope and independence

Run two independent components from the supplied manuscript:

1. The original `refuter` pass searches for counterexamples to central claims under their exact hypotheses. Its prompt, output contract, validation and advisory review remain unchanged.
2. The original reconstruction planner selects critical calculations; two fresh workers independently reconstruct each selected target from definitions, and a third fresh worker reconciles them. Use `reconstruction.md` and the `reconstruction-plan.txt`, `reconstruction-worker.txt`, and `reconstruction-review.txt` prompts and `reconstruction-*.v1` contracts.

The second component runs whether or not the first finds a candidate error. Do not feed refuter findings into the planner or reconstruction workers, and do not feed reconstruction findings into the refuter. The coordinator combines completed reviewed outputs afterward. Serial execution is acceptable; fresh contexts and blindness are required. Preserve the user's resource limits and record unselected critical calculations. Do not hardcode known errors, paper locations, or expected results.

The reconstruction retains concrete conventions, model identification, the sign-producing or other calculation, and the downstream application. Both reconstruction workers receive the same mathematical assignment and original procedure. Source agreement alone cannot close a target. Do not relax these requirements to an optional calculation field or replace one derivation with a general adversarial review.

## Execute

Resolve `<skill>` to the shared `math-paper-verifier` directory. Read `native-execution.md` for the original pass preparation/finalization and advisory review, and `reconstruction.md` for the paired stage. In a desktop app, use native fresh subagents; do not launch provider CLIs.

Prepare the original refuter as one independent component:

```sh
python3 <skill>/run/run_native.py prepare --provider codex \
  --paper <manuscript> --pass refuter --out <run>/refuter
```

Use the actual host provider, input/bundle options and produced prompt path described in `native-execution.md`. Complete that pass's input-integrity validation, output validation, rendering and advisory review. The original refuter's narrower claim-truth scope governs this worker only; it does not suppress local proof defects found by the reconstruction component.

Independently prepare the original reconstruction planner:

```sh
python3 <skill>/run/reconstruction.py prepare-plan --audit-kind reconstruction \
  --paper <manuscript> --out <run>/reconstruction-plan \
  --scope '<central calculations and resource limits requested by the user>'
```

`--audit-kind reconstruction` is optional and is the only supported kind. Repeat `--reference <local-file>` only for explicitly supplied local references. Those references are a recorded condition of the reconstruction component; do not silently change the original refuter's manuscript-only input policy. Both components are offline. Do not fetch missing sources to close a gap.

Dispatch the prepared planner prompt to a fresh worker with no previous results. For every selected target, use `prepare-pair`, dispatch **two distinct fresh derivation workers**, run `check-pair`, then `prepare-review`, dispatch a **fresh mathematical reviewer**, and run `check-review`, exactly as in `reconstruction.md`. Record model/effort, handoffs, hashes and isolation limitations for both components.

An explicit counterexample-only request runs just the original refuter. An explicit reconstruction-only request runs just the original reconstruction stage. Otherwise central-refutation requests include both. Do not add global/decomposed or external-source passes to this bounded shortcut without a full-audit request. If invoked alongside another requested reconstruction, one stage may serve both only when its predeclared scope covers the central calculations; preserve its blindness and do not duplicate completed targets merely to increase agreement.

The reconstruction component requires native fresh workers. A CLI-only legacy refuter cannot be labeled the completed combined workflow. Missing workers, unresolved targets or unavailable advisory reviews remain visible; do not silently replace a required component.

## Combine and report

Keep the original refuter output and each reconstruction plan, pair and review as separate authoritative artifacts. Apply `reconstruction.md` and `merge-protocol.md` when making the combined report. Merge only mathematically reviewed reconstruction defects into findings; do not promote unresolved calculations to errors or demand theorem falsity before reporting a local proof failure. Use the ordinary severity rubric for demonstrated consequences, without inventing a repair or declaring irreparability merely because none is known.

Report the counterexample search outcome separately from the reconstruction findings and coverage. A failed proof step does not imply that the theorem is false, and an inconclusive counterexample search does not validate the proof. Preserve all unresolved/unreviewed critical calculations prominently, even if the original refuter's finding-based verdict is accept. Link both components and their review evidence. This combined targeted check is not a full paper audit, and a successful development regression is not a reliability estimate.
