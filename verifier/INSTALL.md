# Installing Math Verifier v.1.0

The repository ships one shared implementation in `verifier/math-paper-verifier/`
and two small shortcut skills: a central refuter and a user-specified focused
check. Codex app, Codex CLI, and Claude Code use the same content. Desktop apps
default to native subagents; terminal and automation use can use the
provider-specific CLI launchers.

All paths need Python 3.10+ for local helpers. PDF input also requires `pypdf`;
source and plain-text inputs have no extra Python dependency.

- **Desktop apps:** a signed-in Codex app or Claude Code's desktop **Code**
  surface with fresh subagents and local file tools. No separate provider CLI
  installation, CLI login, API key, or custom agent installation is required.
  External checks use the app's permitted web tools.
- **Direct CLI launchers:** an authenticated `codex` or `claude` executable.

Verification inherits runtime model defaults; the skill does not pin experiment
settings. A host without the required tools will report the limitation rather
than silently fall back to a CLI.

## Codex app and Codex CLI

From the repository root:

```sh
python3 verifier/install.py codex
```

Installs all three entries into `~/.agents/skills/`.

## Claude Code (desktop Code surface or terminal)

```sh
python3 verifier/install.py claude
```

Installs all three entries into `~/.claude/skills/`. The installer creates
symlinks, so keep the repository at its installed location. It does not install
or invoke a provider CLI. Already-correct links are left unchanged; existing
copies or different/broken links are reported before any links are created.
Move conflicting entries outside the skills directory to preserve local edits,
then rerun. To choose a different installation directory, add
`--skills-dir /absolute/path/to/skills`.

Restart the app or open a new session to refresh skill discovery.

After installation, open a local app task and ask: “Use math-paper-verifier to
verify this paper using app-native workers.” Desktop use chooses this path
even if a CLI is installed. See [native execution](math-paper-verifier/references/native-execution.md)
for capability requirements and [the skill README](math-paper-verifier/README.md)
for direct CLI commands.

## Full review or a focused shortcut

Use `math-paper-verifier` for the standard multi-pass review, or choose one
shortcut for a single mathematical check:

| Skill name | Runs only |
| --- | --- |
| `math-paper-verifier-central-refuter` | A search for counterexamples to central claims |
| `math-paper-verifier-focused` | A check of the mathematical aspect and scope you specify |

Invoke with `$` in Codex or `/` in Claude Code, followed by the paper path:

```text
Codex:       $math-paper-verifier-central-refuter paper.pdf
Claude Code: /math-paper-verifier-central-refuter paper.pdf
```

For a focused check, add what you want examined. For example, in Claude Code:

```text
/math-paper-verifier-focused paper.tex — check the equations in Section 3
/math-paper-verifier-focused paper.tex — check boundary and degenerate cases
/math-paper-verifier-focused paper.tex — check whether the quotient construction is well-defined
```

Use `$` instead of `/` in Codex. These are examples of the same general pass,
not separate modes or an exhaustive list. You can also ask in ordinary
language: “Use math-paper-verifier-focused to check all changes in quantifier
order in this paper.” If you omit the focus, the skill asks what to check.

Each shortcut uses the shared validation, readable finding locations,
advisory review, and JSON plus
Markdown reports. These checks do not verify outside sources and are not a
complete paper review. Ask the main skill for multiple passes or other custom
checks. Shortcuts require the sibling `math-paper-verifier` folder; if copying
instead of linking, copy all three skill folders together.

## Execution and evidence

Claude Code support is supplied for public usage. The repository's main
experiment table reports Codex runs and does not claim that comparison was
reproduced with Claude.

Web access is automatic only for registry-declared source-verification passes.
Native runs check prepared-input integrity and shared output contracts, with
host-dependent isolation and activity-recording limitations visible in the
report. CLI runs additionally use their provider-specific transcript gates.
Both paths retain advisory source/conduct review. Keep answer keys, prior audits,
and private notes outside the submitted paper or source directory.

## Updating an older installation

The skill was previously installed as `ensemble-paper-audit`. If you used that
name, inspect the old entry in your runtime's skills directory first. Remove
only the old symlink, or move a copied directory outside the skills directory
to preserve any local changes, then install `math-paper-verifier` with the
commands above. Restart the app or open a new session to refresh discovery.
The new invocation name is `math-paper-verifier`; existing reports remain valid.

If `math-paper-verifier` is already linked to this checkout, rerun the installer
to add the two shortcuts. No existing core link needs to be removed.

The earlier `math-paper-verifier-equations` and
`math-paper-verifier-boundary-cases` shortcut entries have been replaced by
`math-paper-verifier-focused`. If you installed those earlier entries, the
installer reports them but does not remove them. Move them outside the skills
directory to preserve any local copies or edits, then refresh the app/session.
