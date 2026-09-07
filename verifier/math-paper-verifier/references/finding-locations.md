# Reader-facing finding locations

For each finding, identify where a reader should look in the paper, not just
where an editor should look in the source. Use the shared location object in
findings, external-obligation locations/use sites, and argument-spine locations.

- Give the section number/title and the relevant named statement when available:
  `statement: "Remark 3.2"`, `statement: "Lemma 4.1"`, or
  `theorem: "Theorem 2.1"`. Do not duplicate the same statement in both fields.
- For a proof error, name the proof in `proof`, including the direction, case,
  step, or paragraph when useful: `"Proof of Theorem 2.1, necessity direction"`.
- Include an equation number in `equation` when relevant and a short, distinctive
  `quote` anchoring the exact problematic step. Do not use a theorem number alone
  for an error hidden in a long proof.
- Retain `line_start`/`line_end` when available. Use `source_file` for the relative
  path within the staged paper inputs; `section` is for the paper's section, not
  a filename. Use `source_label` for a literal TeX label, not its imagined number.

## PDF input or a supplied matching compiled PDF

Use `page` for the one-based physical PDF page, including title/front-matter
pages. The `===== PDF PAGE N =====` markers in extracted text provide this index.
Use `page_label` separately for a printed or viewer label when observed; PDF
metadata labels need not agree with the printed footer. For a multi-page span,
identify the page containing the problematic step and describe its context.
Extracted-text line numbers are not printed-page line numbers.

Read statement/equation identifiers from the supplied PDF or its unambiguous
extracted text. If extraction damages a heading or formula, inspect the PDF with
available tools; otherwise omit the uncertain identifier and record the
limitation. A textless page is unreviewed unless visually inspected.

When source and a compiled PDF are supplied together, verify that the local
passage matches before attaching the PDF's page or numbering to a source
finding. The runner records both inputs but does not establish that they are
the same revision. Source is the audit target. If the passage differs, retain
the source finding and record the mismatch in `unresolved_checks`; do not
silently substitute the PDF's mathematics or invent a correspondence.

## Source-only input and missing identifiers

Use explicit titles, labels, recognizable proof descriptions, and quotations.
Do not guess PDF pages or compiled numbering by counting TeX environments:
custom counters, shared numbering, macros, and appendices can change it. Do not
compile the paper or run submitted build files just to obtain locations. If an
identifier cannot be established, omit it and keep the usable source/quote
anchors. Say so in `unresolved_checks` when this hinders locating the finding.
Missing numbered locations are a reporting limitation, not a retry trigger.

## Delegation and source verification

Pass this location guidance to region workers along with their assigned spans.
Preserve their supported structural and source anchors when consolidating
findings. During external inventory, carry readable locations into both
`location` and `use_site` and into external-check coverage notes. The independent
source-verification worker must copy manuscript locations from that inventory:
it must not retrieve the manuscript or receive its PDF to fill missing anchors.
Locations within an outside source belong in the source evidence, not in the
manuscript finding's `location`.
