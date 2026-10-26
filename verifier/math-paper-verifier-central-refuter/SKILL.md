---
name: math-paper-verifier-central-refuter
description: Search for counterexamples to central mathematical claims and independently reconstruct the critical calculations supporting them. Use for central refutation with paired reconstruction; explicit counterexample-only requests run just the original refuter.
metadata:
  version: "v.1.0"
---

# Math Verifier v.1.0 — Central Refuter

Run the original central-claim refuter and the original paired reconstruction
procedure as independent components. This is a bounded central check, not a full
paper review.

Read [the shared skill](../math-paper-verifier/SKILL.md) and
[central refutation with reconstruction](../math-paper-verifier/references/central-reconstruction.md)
completely before acting. Resolve these paths relative to this file, not the
working directory. The sibling `math-paper-verifier` installation is required;
if it is missing, explain how to install the complete bundle instead of
inventing a fallback implementation.

The reconstruction uses a fresh planner, two independent derivations per
selected calculation, and a fresh mathematical reviewer. Both derivation workers
receive the same assignment. Retain concrete conventions, model identification,
the calculation, and its downstream application. Neither component receives the
other's findings before completion. Report theorem refutation, local proof
failure, and unresolved calculations separately.

Both components are offline. Reconstruction may use explicitly supplied local
references, recorded as inputs. It requires native fresh subagents; a CLI-only
refuter is not the completed combined workflow. Do not add global, decomposed,
or external-source passes unless requested.

For an explicit **counterexample-only** request, run only `--pass refuter` using
[shortcut execution](../math-paper-verifier/references/shortcut-execution.md).
Already delegated a prepared worker task? Execute only that task and its supplied
inputs; do not restart the workflow or read another pass's results.
