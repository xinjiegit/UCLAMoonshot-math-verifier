#!/usr/bin/env python3
"""Launch an auditable pass through the Claude Code provider adapter."""

from claude_code_adapter import *  # noqa: F403 - compatibility exports


if __name__ == "__main__":
    raise SystemExit(main())  # noqa: F405
