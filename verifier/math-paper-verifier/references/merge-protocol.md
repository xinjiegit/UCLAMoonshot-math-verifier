# Merge protocol

Merge completed pass outputs only after validating each one.

Keep each pass's advisory safeguard review separate from its mathematical
findings. Include the review paths when rendering the final Markdown report;
do not count advisory concerns as mathematical errors, suppress findings because
of a suspicious-activity flag, or silently omit unavailable reviews. Integrity
failures are separate and cannot be overridden by a favorable advisory.

## Match defects

Two findings match only when both their location and mathematical failure mechanism match. Nearby findings are not duplicates if they concern different mechanisms. Never use pass-local finding IDs for matching.

For a match, retain the clearest claim/problem explanation, union nonduplicative evidence and unresolved checks, and preserve the most informative repair task. Reassess confidence from the combined evidence; corroboration may raise confidence, but disagreement must remain visible.

Reassess the class from the combined record using the output contract's minimum-
adequate-repair rubric. Do not inherit the highest source-pass class by default,
and do not promote a finding because several passes reported it. Corroboration
supports confidence; severity depends on the repair and its mathematical effect.

Keep every unmatched finding. A singleton is not weaker merely because only one complementary pass detected it.

Retain complementary supported location anchors: section/statement, proof
context, equation, PDF page/label, source file/lines/label, and a precise quote.
Follow `finding-locations.md`. Do not replace a rich location with a line-only
one during deduplication. Resolve conflicting anchors against the supplied
paper; if unresolved, omit the disputed anchor and describe the uncertainty.
Never fetch the manuscript to enrich a source-verification worker's locations.

## Rank and classify

Order findings by:

1. `central_unsalvageable_error`
2. `noncentral_unsalvageable_error`
3. `major_repairable_gap`
4. `minor_repairable_gap`
5. `cosmetic_or_exposition_only`

Within a class, order by centrality and then confidence. Reassign `F1`, `F2`, ... and renumber evidence and repair-task IDs so references remain consistent.

Recompute the verdict from the merged findings using the
[output-contract verdict rules](output-contract.md#verdict), not a vote or the
input reports' verdicts. A `central_unsalvageable_error` requires `reject`;
otherwise a `major_repairable_gap` requires `major_revision`. With neither,
`noncentral_unsalvageable_error` or `minor_repairable_gap` requires
`minor_revision`; empty or cosmetic-only findings permit `accept`. Do not
classify a missing but plausibly supplyable substantive argument as unsalvageable.

## Provenance file

Write `merge-map.json` separately:

```json
{
  "schema_version": "ensemble-paper-audit.merge-map.v1",
  "findings": [
    {
      "finding_id": "F1",
      "sources": [
        {"pass": "global", "finding_id": "F2"},
        {"pass": "decomposed", "finding_id": "F7"}
      ]
    }
  ],
  "counts": {"global_only": 0, "decomposed_only": 0, "both": 1}
}
```

Optional passes use `argument_spine`, `display_sweep`, `boundary_clause_sweep`, `refuter`, `citation`, or `external_verification` as the pass label. Merge only an argument-spine pass's `verifier-output.json`; keep its `argument-spine.json` sidecar separate. Keep external obligations, source resolutions, and the fetch log outside `verifier-output.json`; only the external-verification pass's mathematical findings are merged. A `verified` source never deletes or downgrades an internal mathematical finding. Never add provenance fields to `verifier-output.json`.
