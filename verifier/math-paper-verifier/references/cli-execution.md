# CLI execution

Use this path in terminal/automation environments or when the user requests
the isolated CLI runner. Desktop app use defaults to `native-execution.md`.
The corresponding `codex` or `claude` executable must be installed and
authenticated; Python 3.10+ is also required.

Resolve `<skill-dir>` to the installed skill. Set `<runner>` to
`run/run_codex.py` or `run/run_claude_code.py`. Work from a writable directory,
not the installed skill, so output goes to `./paper-audit-output/`.
Do not set `--model` or `--effort` unless the user requests an override.

## Mathematical passes

```sh
python3 <skill-dir>/<runner> --paper <paper-or-source-dir> --pass global
python3 <skill-dir>/<runner> --paper <paper-or-source-dir> --pass decomposed
```

Each invocation prepares its own input directory and provider process. The
Codex launcher uses a fresh private user configuration; the Claude launcher
restricts tools and settings. Codex sessions persist within that run so nested
workers can start; the launcher does not use `--ephemeral`. Available session
records are copied to `sessions/` in the run output, without authentication or
configuration files. Treat these records as private paper data, not release assets.
Provider-bundled instructions may still be present. Captured event streams
support post-run inspection, but these controls are not a universal operating-system
read sandbox or a guarantee of complete child activity capture.

Codex uses the top-level `web_search` setting and the compatibility alias
`agents.max_threads` when `--max-agent-threads` is supplied. CLI capabilities
and available model names depend on the installed version and account; an
upgrade does not replace these launcher settings. Use the actual supported
model identifier when requesting an override. A startup failure must be
reported, not silently retried with another model or claimed as a completed pass.

For source input with a user-supplied compiled counterpart, add
`--reference-pdf <compiled.pdf>` to the mathematical and inventory runs. Both
providers stage its page-aware text and original PDF for location matching,
without compiling TeX. PDF-only input needs only `--paper <paper.pdf>`. Follow
`finding-locations.md`; do not supply a reference PDF to external-verification.

Run the appropriate provider gate, then validate:

```sh
python3 <skill-dir>/run/audit_codex_run.py <run-directory>
# For Claude instead: python3 <skill-dir>/run/audit_claude_run.py <run-directory>
python3 <skill-dir>/scripts/validate_output.py <run-directory>/verifier-output.json
```

Run the separate advisory reviewer after each completed pass:

```sh
python3 <skill-dir>/run/run_safeguard_review.py --run <run-directory>
```

Read `safeguard-review.md` for model defaults, unavailable reviews, and reporting.

## Source checks

```sh
python3 <skill-dir>/<runner> --paper <paper-or-source-dir> \
  --pass external-obligations --coverage-input <coverage.json>
python3 <skill-dir>/scripts/validate_external_artifacts.py \
  <inventory-run>/external-obligations.json --coverage-input <coverage.json>
python3 <skill-dir>/<runner> --paper <paper-or-source-dir> \
  --pass external-verification --obligations <inventory-run>/external-obligations.json
```

Gate external verification with `--citation-mode`, then validate ordinary and
external output artifacts. The source verifier receives the inventory rather
than the manuscript. The provider gate displays observed web activity and the
authored log for comparison, not exact equality checking.
One retrieved source may support several obligations: keep one actual fetch
record and list its use under each applicable resolution. Do not invent duplicate
fetches. Missing printed bibliography data remains an explicit inventory/source
limitation, not a reason to fabricate a reference or rerun the paper review.

## Optional passes

```sh
python3 <skill-dir>/<runner> --paper <paper> --pass argument-spine
python3 <skill-dir>/<runner> --paper <paper> --pass refuter
python3 <skill-dir>/<runner> --paper <paper> --pass focused-sweep \
  --focus "equations in Section 4"
python3 <skill-dir>/<runner> --paper <paper> --pass citation
```

Validate argument-spine output with `validate_argument_spine.py`. Claude Code
focused sweeps alone may receive `--allow-compute`; Codex needs no equivalent
flag for read-only mechanical computation. Paper-supplied code remains out of
scope without authorization. Citation passes are automatically web-enabled and
require a fetch log. The same gate, validation, advisory review, merge, and
Markdown rendering requirements apply to optional passes.
