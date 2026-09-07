# Output contract

Write `verifier-output.json` in the repo's `verifier-output.v1` shape, so
a fan-out audit is directly comparable with any single-pass audit of the same
paper (`diff <(jq . A/verifier-output.json) <(jq . B/verifier-output.json)`).

This JSON is the authoritative audit artifact. After it validates, generate the
human-readable companion without asking a model to rewrite the findings:

```sh
python3 <bundle>/scripts/render_report.py <path>/verifier-output.json
```

The renderer writes `verifier-report.md` beside the JSON by default and embeds
the source JSON hash. Regenerate it whenever the JSON changes.

The authoritative synchronized schemas are `verifier-output.schema.json` and
`common.schema.json` in this runtime's supplied contract/schema directory.
Validate with the bundled script, which locates that directory automatically
and checks both schema and ranking:

```sh
python3 <bundle>/scripts/validate_output.py <path>
```

Add `--schema-only` when checking another arm's output: ranking is this skill's
convention, not part of the contract, and e.g. `one_shot` emits unranked findings.

## Shape

- `verdict` ∈ `reject`, `major_revision`, `minor_revision`, `accept`
- `summary` — one paragraph
- `findings[]` — each with `finding_id` (`F1`, `F2`, …), `class`, `location`,
  `claim_under_review`, `problem`, `centrality`, `repairability`, `evidence`,
  `confidence`, `unresolved_checks`, `repair_tasks`
- `coverage_notes` — `reviewed_regions`, `unreviewed_or_difficult_regions`,
  `external_checks_not_performed`

The schema enforces verdict/class consistency (e.g. `reject` requires a
`central_unsalvageable_error`), and forbids paper identity, lineage, or run
metadata. There is no uncertainty class: express doubt via `confidence` and
`unresolved_checks`.

## Verdict

Choose the overall verdict from the findings using these rules in order:

1. `reject` if any finding is a `central_unsalvageable_error`.
2. Otherwise, `major_revision` if any finding is a `major_repairable_gap`.
3. Otherwise, `minor_revision` if any finding is a
   `noncentral_unsalvageable_error` or `minor_repairable_gap`.
4. Otherwise, `accept`: the findings are empty or only
   `cosmetic_or_exposition_only`.

A noncentral unsalvageable error does not by itself require major revision;
its finding class and repairability remain unchanged. The verdict is not based
on a finding count. A coexisting major repairable gap still requires major
revision, and a central unsalvageable error still requires rejection. The
finding ranking below is unchanged and is distinct from the overall verdict.

This revises the earlier mapping of noncentral unsalvageable errors to major
revision. Historical reports retain their original verdicts; do not silently
rewrite saved or experimental artifacts to satisfy this updated contract.

## Reader-facing locations

Follow [finding-locations.md](finding-locations.md) for all passes and merges.
Prefer the references a reader can find in the paper, alongside source anchors:

```json
{
  "section": "4. Compactness",
  "theorem": "Theorem 4.3",
  "proof": "Proof of Theorem 4.3, necessity direction, second paragraph",
  "equation": "(17)",
  "page": 12,
  "page_label": "10",
  "source_file": "source/sections/estimate.tex",
  "source_label": "thm:compactness",
  "line_start": 210,
  "line_end": 218,
  "quote": "Applying the endpoint estimate gives"
}
```

This is an illustrative location, not a benchmark finding. Include only fields
supported by the supplied inputs. `statement` accommodates remarks, lemmas,
definitions, propositions, and other named statements; `theorem` remains valid.
`page` is the physical PDF page (one-based), while `page_label` is a separately
observed printed/viewer label. A TeX label is not compiled numbering.

The new `statement`, `proof`, `page_label`, `source_file`, and `source_label`
fields are optional additions to the shared location schema. Existing v1
reports, including source-only locations and filenames in `section`, still
validate. New reports use `source_file` for paths and `section` for section
titles. Older copies of the validator may reject the new fields; use the
validator bundled with this skill. Unknown numbers remain omitted, not grounds
for repeating verification. The renderer does not infer missing locations.

## Classes

Exactly one per finding:

- `central_unsalvageable_error`
- `noncentral_unsalvageable_error`
- `major_repairable_gap`
- `minor_repairable_gap`
- `cosmetic_or_exposition_only`

Distinguish centrality from repair effort. A missing substantive argument is a
**major repairable gap** when an honest new argument could preserve the claim —
not unsalvageable merely because the repair is hard. Centrality is a
whole-paper judgment: trace the dependency path from the finding to the
headline claim.

Classify severity by the **minimum adequate repair**, after checking the full
context, and by what that repair changes:

- Use `major_repairable_gap` only when the repair needs substantive new
  mathematics, materially changes the statement or scope of a principal
  result, or requires reworking multiple dependent parts of the argument.
  A defect is not major merely because it occurs in a central theorem.
- Use `minor_repairable_gap` when a local correction or short addition within
  the paper's existing method establishes the claim while leaving the
  principal results and proof architecture intact.
- Use `cosmetic_or_exposition_only` when the intended correction is forced by
  the surrounding argument and changes no mathematical reasoning, or when the
  concern is clarity, notation, or presentation rather than validity.

Do not report a standard convention, a routine omitted calculation, or a
preference for more explicit exposition as a mathematical gap unless its
absence creates a concrete ambiguity or invalidates a stated inference. If no
meaningful correction is needed, omit the candidate. When evidence supports a
defect but not the higher of two plausible severity classes, use the lower
supported class and record the remaining uncertainty. The repairability
rationale must explain both the smallest adequate repair and its effect on the
paper's claims.

## Ranking

`findings` must be ordered **most severe first**, in class order:

```
central_unsalvageable_error
noncentral_unsalvageable_error
major_repairable_gap
minor_repairable_gap
cosmetic_or_exposition_only
```

Within a class, order by centrality, then confidence. A human reads from the top
and stops when it stops being worth it — the ordering is the product. Ranking is
also what makes keeping safe, but low placement is not a reason to retain a
pedantic non-defect. Rank supported findings honestly and apply the reportability
threshold above before keeping a candidate.
