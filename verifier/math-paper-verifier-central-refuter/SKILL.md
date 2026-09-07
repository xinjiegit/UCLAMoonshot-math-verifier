---
name: math-paper-verifier-central-refuter
description: Search for counterexamples to central claims in a mathematical paper using Math Verifier's refuter pass only. Use when the user requests central refutation or a counterexample-only check, rather than a full paper review. Accepts the same paper inputs as math-paper-verifier in Codex and Claude Code, including desktop apps without a separate provider CLI.
metadata:
  version: "v.1.0"
---

# Math Verifier v.1.0 — Central Refuter

Run only the existing `refuter` pass (`--pass refuter`). Look for decisive
counterexamples to central claims; this is not a full paper verification.

Read [the shared skill](../math-paper-verifier/SKILL.md) and
[shortcut execution](../math-paper-verifier/references/shortcut-execution.md)
completely before acting. Resolve these paths relative to this file, not the
working directory. The sibling `math-paper-verifier` installation is required;
if it is missing, explain how to install the complete bundle instead of
inventing a fallback implementation.

Invoking this shortcut is an explicit **refuter-only** request. Keep the shared
skill's execution routing, fresh-worker boundaries, validation, advisory review,
and JSON/Markdown reporting. Do not add global, decomposed, equation, boundary,
or external-source passes unless the user also requests them. If already a
delegated worker, execute only the assigned task, as the shared skill requires.
