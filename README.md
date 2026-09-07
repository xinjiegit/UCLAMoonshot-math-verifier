# UCLA Moonshot Math Verifier v.1.0

Structured verification for mathematical papers.

UCLA Moonshot Math Verifier v.1.0 (`math-paper-verifier`) is a reusable, provider-neutral skill for
checking mathematical papers in Codex and Claude Code. It combines whole-paper
reasoning with systematic section-by-section verification, optional targeted
checks, and verification of cited sources.

The output includes a human-readable Markdown report and structured JSON.
Findings include severity, supporting evidence, and reader-facing locations
such as sections, theorems, proofs, equations, and PDF pages where these can be
established. Findings are candidates for expert review, not a certification of
correctness.

## Install

Clone this repository or download and extract the skill-only `math-verifier.zip`
release asset. Open a terminal in the folder containing `verifier/` (the repository
root or the extracted `math-verifier/` folder). Choose your provider:

```sh
# Codex app or CLI
python3 verifier/install.py codex

# Claude Code desktop Code surface or CLI
python3 verifier/install.py claude
```

Python 3.10+ is required for local helpers; PDF input additionally needs `pypdf`.
Desktop use does not require a separately installed provider CLI or an API key.
The installer links the main skill and both shortcuts into your provider's
skills directory, so keep the repository or extracted folder in place. It does not overwrite
existing copies or conflicting links.

See the [installation guide](verifier/INSTALL.md) for requirements, custom
destinations, and upgrades. You do not need to build the website to use the
skill.

## Review a paper

Start a new local session with access to your paper and ask:

> Use math-paper-verifier to verify paper.pdf and give me a findings report.

You can also supply TeX sources, Markdown, or text. If you have both the TeX
source and its matching compiled PDF, provide both to help establish readable
finding locations. Open `verifier-report.md` for the report;
`verifier-output.json` retains the structured findings.

For a narrower task, use one of the included shortcuts:

| Skill | Purpose |
| --- | --- |
| `math-paper-verifier` | Full multi-pass paper verification |
| `math-paper-verifier-focused` | Check the aspect and scope you specify, such as equations or boundary cases |
| `math-paper-verifier-central-refuter` | Search for counterexamples to central claims |

Invoke a shortcut with `$` in Codex or `/` in Claude Code, followed by the paper
and, for a focused check, what to examine. See the
[skill documentation](verifier/math-paper-verifier/README.md) for examples,
execution details, report interpretation, and direct CLI commands.

## What's included

Both the repository and the skill-only `math-verifier.zip` release asset include
[`verifier/`](verifier/): the shared skill, two shortcuts, installer, and helpers
for app-native and CLI execution, together with this README and the
[MIT License](LICENSE).

The full repository (including GitHub's source ZIP) additionally includes
`site/`, containing the website and video, and `.github/workflows/`, containing
the GitHub Pages deployment and release packaging workflows. These are
intentionally omitted from the skill-only ZIP; they are not needed to install
or use the skill.

This is the software release. Experimental datasets, paper collections, run
outputs, evaluation scripts, and the technical report are not included.
**Technical report coming soon.** The website summarizes the controlled
evaluation motivating the design; its full protocol and analysis will be
presented in the report. The reported comparison used Codex; Claude Code
support does not imply that the experiment has been reproduced with Claude.

## Review and evidence

Review candidate findings against the paper and relevant sources before
treating them as errors. App-native workers use the host's available permissions
and activity exports; the report discloses missing records and isolation
limitations. CLI execution additionally retains provider event streams.
The [skill documentation](verifier/math-paper-verifier/README.md) explains the
current execution policies and independent advisory review.

## Team

**Student researchers:** Xinjie He, Hyunsik Chae, Alex Taylor, Kyle Hess.

**Principal investigators:** Kai-Wei Chang, Raghu Meka, Violet Peng, Amit Sahai,
Terence Tao, Wei Wang.

## License

The original skill instructions, code, documentation, and website source are
released under the [MIT License](LICENSE). Third-party dependencies retain their
respective licenses.
