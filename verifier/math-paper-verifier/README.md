# Math Verifier v.1.0

Structured verification for mathematical papers.

`math-paper-verifier` is one provider-neutral skill for verifying mathematical
papers with mutually blind verification passes. Desktop apps use their own
subagents without a separately installed provider CLI. Optional CLI launchers provide process
control for terminal/automation use. Both paths share the mathematical prompts,
contracts, preparation, and validators across Codex and Claude Code.

The standard audit runs:

1. a whole-paper mathematical pass;
2. a forced fine-grained decomposition pass;
3. a blind inventory of external obligations; and
4. an independent-source verification pass with bounded web access.

Each pass receives staged inputs and a fresh worker context. Blind passes
are kept separate from one another's results. CLI runners capture event streams
and use provider-specific process controls; native app runs preserve whatever
activity evidence the host exposes and explicitly report missing evidence or
instruction-only restrictions. Results must pass input-integrity and output
validation. A separate reviewer, using a lightweight model where available, reviews
search scope and suspicious activity, surfacing concerns for human judgment
without automatically rejecting or repeating the verification.

## Architecture

```text
math-paper-verifier/
├── SKILL.md
├── contract/ and references/       shared audit policy and prompts
├── scripts/                        validators and Markdown report renderer
└── run/
    ├── common.py                   pass registry and input/isolation helpers
    ├── run_codex.py                thin public launcher
    ├── run_claude_code.py          thin public launcher
    ├── run_native.py              CLI-free app-worker preparation/validation
    ├── codex_adapter.py            Codex process and event handling
    ├── claude_code_adapter.py      Claude Code process and event handling
    ├── audit_codex_run.py          Codex transcript gate
    ├── audit_claude_run.py         Claude Code transcript gate
    └── run_safeguard_review.py     independent advisory model review
```

The provider adapters differ only where the host interfaces differ: command
invocation, tool permissions, event parsing, and transcript gating. The
mathematical workflow and output contracts have one authority.

Two sibling skill folders provide targeted entry points:
`math-paper-verifier-central-refuter` and `math-paper-verifier-focused`.
They contain only instructions and UI
metadata; all prompts, runners, validation, and reporting remain here.

The public release is **Math Verifier v.1.0** and the installable skill name is
`math-paper-verifier`. Existing JSON schema identifiers (`ensemble-paper-audit.*`
and `urn:ensemble-paper-audit:*`), versioned prompt headers, and output filenames
are retained for compatibility with saved runs. Historical experiment records
retain their original terminology; these identifiers are not installation names.

## Requirements

- Python 3.10 or newer.
- For app-native use: Codex app or Claude Code's desktop Code surface, signed in,
  with fresh subagents and local file tools. Source checking also needs web tools.
  No separate `codex` or `claude` CLI, API key, or custom agent installation.
- For direct CLI launchers only: an authenticated `codex` or `claude` CLI.
- For PDF input: `pypdf` (`python3 -m pip install pypdf`). TeX, Markdown, and
  text inputs need no additional Python package.

Provider defaults determine the verification model and reasoning effort unless
the user explicitly supplies an override. The separate safeguard reviewer uses
a lightweight model, configurable independently. The repository's experiment table reports
Codex runs; including the Claude Code launcher is not a claim that the main
comparison was reproduced with Claude.

## Install

From the repository root, install the main skill and both shortcuts.
Codex app and Codex CLI use the same installation:

```sh
python3 verifier/install.py codex
```

Claude Code:

```sh
python3 verifier/install.py claude
```

The installer creates sibling symlinks and leaves already-correct links alone.
It never overwrites an existing copy or different link. See the
[installation guide](../INSTALL.md) for custom destinations, upgrades, and
invocation examples. This core folder remains usable on its own; the optional
shortcuts require it alongside them.

## Focused shortcuts

| Skill name | Shared pass selector |
| --- | --- |
| `math-paper-verifier-central-refuter` | `refuter` |
| `math-paper-verifier-focused` | `focused-sweep --focus "what to check"` |

For example, use `$math-paper-verifier-focused paper.tex — check the equations
in Section 3` in Codex, or the same invocation with `/` in Claude Code. The focus
is free-form: boundary cases, quantifier dependencies, or whether a particular
construction is well-defined are other examples, not a fixed list of options.
The skill asks what to check if no focus was supplied. These entry points run
only the requested mathematical check, followed by shared validation, advisory review,
and JSON/Markdown reporting. They do not run the standard multi-pass review or
fetch outside sources. Use `math-paper-verifier` for a full review or a custom
combination of passes. See [shortcut execution](references/shortcut-execution.md)
for the shared handoff procedure.

The direct CLI aliases `display-sweep` and `boundary-clause-sweep` remain
compatible presets of `focused-sweep`; they do not have separate skill folders.

## Use in a desktop app

Open a local task with your paper and ask the installed skill to verify it:

> Use math-paper-verifier to verify this paper using app-native workers.

Native execution is the default in both desktop apps, even when a provider CLI
is installed. The app coordinates independent verification and advisory workers;
the bundled Python helpers only prepare, validate, and render local files. If a
host disallows nested subagents, the main app coordinates the small-region
workers itself. See [native execution](references/native-execution.md) for the
handoffs and evidence limitations. This requires the Code surface in Claude, not
an ordinary Chat conversation.

The report distinguishes app-native execution from CLI execution. Separate
contexts do not guarantee filesystem isolation, disabled inherited settings, or
a complete captured transcript. Missing evidence stays visible even when the
reviewer identifies no concern. If required host tools are unavailable, the
skill explains the limitation instead of silently installing or invoking a CLI.

## Direct CLI launcher use

From a writable working directory, choose one launcher using the skill's
absolute path:

```sh
python3 /path/to/math-paper-verifier/run/run_codex.py \
  --paper ~/papers/mypaper.tex --pass global
python3 /path/to/math-paper-verifier/run/run_claude_code.py \
  --paper ~/papers/mypaper.tex --pass global
```

Run the global and decomposed passes separately and keep them blind:

```sh
python3 /path/to/math-paper-verifier/run/run_codex.py \
  --paper ~/papers/mypaper.tex --pass global
python3 /path/to/math-paper-verifier/run/run_codex.py \
  --paper ~/papers/mypaper.tex --pass decomposed
```

Then gate and validate each result:

```sh
python3 /path/to/math-paper-verifier/run/audit_codex_run.py \
  paper-audit-output/RUN_DIRECTORY
python3 /path/to/math-paper-verifier/scripts/validate_output.py \
  paper-audit-output/RUN_DIRECTORY/verifier-output.json
python3 /path/to/math-paper-verifier/scripts/render_report.py \
  paper-audit-output/RUN_DIRECTORY/verifier-output.json
```

The final command validates the JSON again and writes a human-readable
`verifier-report.md` beside it. `verifier-output.json` remains authoritative;
the Markdown report records its SHA-256 hash and should be regenerated rather
than edited independently.

Use `audit_claude_run.py` for Claude Code output. Source-verification runs add
`--citation-mode` to the provider gate and must also pass
`validate_external_artifacts.py`. In citation mode, the provider gate displays
the transcript-observed web activity and the model-authored fetch log together
for human comparison; it does not require exact automated correspondence.

After each completed pass, run the separate advisory reviewer:

```sh
python3 /path/to/math-paper-verifier/run/run_safeguard_review.py \
  --run paper-audit-output/RUN_DIRECTORY
```

It selects the run's provider, defaults to `gpt-5.6-luna` (Codex) or `haiku`
(Claude Code), and accepts `--model` for the reviewer alone. It writes
`safeguard-review.json` and `safeguard-review.md`, preserving the input and reviewer
transcripts. Search terms are suggestions, not an allowlist. Source independence
and path/command-pattern warnings are reviewed in context. Missing or failed
reviews are reported as unavailable, with no automatic retries. See
[safeguard review](references/safeguard-review.md) for limits and provenance.

Re-render after review to include its advisory section. The renderer discovers a
sibling `safeguard-review.json`; for merged reports, repeat `--safeguard-review
/path/to/pass/safeguard-review.json` for every included pass. Advisory concerns
are kept separate from the ranked mathematical findings.

Run either launcher with `--help` for optional passes and preparation controls.
TeX source directories are reduced to a static allowlisted dependency closure;
submitted build files and paper-supplied code are never executed.

## Interpretation

Math Verifier is an auditing tool, not a proof assistant. `accept` means no
reportable defect was found within the inspected material and coverage limits;
it does not prove the manuscript correct. Domain experts should review findings
before they are presented as errors in a paper.

## Finding locations for human review

New findings include reader-facing section, theorem/lemma/remark, proof-context,
and equation references where they can be established, as well as source lines
and quotations. The Markdown report shows the paper location first and the
source anchor separately. PDF input retains physical page indices; printed or
viewer page labels can be recorded separately.

For TeX or other source input, you can also supply its matching compiled PDF:

```sh
python3 /path/to/math-paper-verifier/run/run_native.py prepare --provider codex \
  --paper ./source --root main.tex --reference-pdf ./paper.pdf \
  --pass global --out ./global-run
```

Use `--provider claude` in Claude Code. Both direct CLI launchers accept the
same `--reference-pdf` option. In an app, simply provide the source and PDF and
ask the skill to use the PDF for finding locations. The source remains the audit
target: workers match each passage before transferring PDF numbering. The
helper does not prove revision correspondence or compile the source. Do not
pass the PDF to external-verification; carry locations through the inventory.

Without a compiled PDF, the skill uses supported titles, proof descriptions,
literal TeX labels, and quotes rather than guessing page or theorem numbers.
Existing JSON reports still validate and render; missing reader-facing anchors
must be added from the paper to the JSON before re-rendering. They cannot be
recovered from line numbers alone. See [location guidance](references/finding-locations.md).
