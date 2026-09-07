#!/usr/bin/env python3
"""Launch an auditable pass through the Codex provider adapter."""

from codex_adapter import *  # noqa: F403 - compatibility exports for callers/tests


if __name__ == "__main__":
    raise SystemExit(main())  # noqa: F405
