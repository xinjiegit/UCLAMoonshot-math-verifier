---
name: math-paper-verifier-focused
description: Check a user-specified mathematical aspect of a paper using Math Verifier's focused pass only. Use for targeted verification, such as equations, boundary cases, quantifiers, or a particular construction, rather than a full paper review. The focus is open-ended, not limited to these examples. Supports Codex and Claude Code, including desktop apps without a separate provider CLI.
metadata:
  version: "v.1.0"
---

# Math Verifier v.1.0 — Focused Check

Run the existing `focused-sweep` pass with `--focus` describing what the user
wants checked and any requested scope. Equations and boundary cases are
examples, not separate procedures or a fixed menu. If the focus is missing or
materially ambiguous, ask what to check; do not silently choose a preset or
run a full review.

Read [the shared skill](../math-paper-verifier/SKILL.md) and
[shortcut execution](../math-paper-verifier/references/shortcut-execution.md)
completely before acting. Resolve these paths relative to this file, not the
working directory. The sibling `math-paper-verifier` installation is required;
if it is missing, explain how to install the complete bundle instead of
inventing a fallback implementation.

Invoking this shortcut is an explicit **focused-pass-only** request. Keep the
shared skill's execution routing, fresh-worker boundaries, validation, advisory
review, and JSON/Markdown reporting. Preserve the user's chosen focus and scope;
do not replace them with a broader checklist. Do not add global, decomposed,
refuter, or external-source passes unless the user also requests them. If already a
delegated worker, execute only the assigned task, as the shared skill requires.
