#!/usr/bin/env python3
"""Install Math Verifier and its shortcuts as non-destructive sibling symlinks."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from pathlib import Path
from typing import Sequence


SKILL_NAMES = (
    "math-paper-verifier",
    "math-paper-verifier-central-refuter",
    "math-paper-verifier-focused",
)
RETIRED_SKILL_NAMES = (
    "math-paper-verifier-equations",
    "math-paper-verifier-boundary-cases",
)
SOURCE_ROOT = Path(__file__).resolve().parent
PROVIDER_DIRECTORIES = {"codex": ".agents", "claude": ".claude"}


class InstallError(Exception):
    """An installation cannot proceed without changing an existing entry."""


def _validate_sources() -> dict[str, Path]:
    """Check every skill's readable frontmatter before touching the destination."""
    sources: dict[str, Path] = {}
    problems: list[str] = []
    for name in SKILL_NAMES:
        source = SOURCE_ROOT / name
        try:
            source = source.resolve(strict=True)
            text = (source / "SKILL.md").read_text(encoding="utf-8")
            lines = text.splitlines()
            if not lines or lines[0].strip() != "---":
                raise ValueError("SKILL.md is missing its YAML frontmatter")
            try:
                end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            except StopIteration:
                raise ValueError("SKILL.md has unclosed YAML frontmatter") from None
            names = [
                match.group(1).strip()
                for line in lines[1:end]
                if (match := re.fullmatch(r"name:\s*(.*?)\s*", line))
            ]
            if len(names) == 1 and len(names[0]) >= 2:
                value = names[0]
                if value[0] == value[-1] and value[0] in "\"'":
                    names[0] = value[1:-1]
            if names != [name]:
                raise ValueError(f"SKILL.md must declare name: {name}")
            if not any(line.strip() for line in lines[end + 1 :]):
                raise ValueError("SKILL.md has no instructions")
            sources[name] = source
        except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
            problems.append(f"{name}: {exc}")
    if problems:
        raise InstallError("Invalid source skills; nothing was installed:\n  " + "\n  ".join(problems))
    return sources


def _matching_link(destination: Path, source: Path) -> bool:
    try:
        return destination.resolve(strict=True) == source
    except (OSError, RuntimeError):
        return False


def install_skills(skills_dir: Path) -> list[tuple[str, Path, bool]]:
    """Install all skills or reject pre-existing conflicts without overwriting them.

    Return (skill name, destination, created) for each skill. Tests and custom
    installations can pass an explicit directory; sources always live beside
    this script, independently of the caller's working directory.
    """
    sources = _validate_sources()
    skills_dir = skills_dir.expanduser().absolute()
    entries: list[tuple[str, Path, bool]] = []
    conflicts: list[str] = []
    try:
        for name, source in sources.items():
            destination = skills_dir / name
            try:
                existing = destination.lstat()
            except FileNotFoundError:
                entries.append((name, destination, True))
                continue
            if stat.S_ISLNK(existing.st_mode) and _matching_link(destination, source):
                entries.append((name, destination, False))
            else:
                conflicts.append(str(destination))
    except OSError as exc:
        raise InstallError(f"Cannot inspect destination; nothing was installed: {exc}") from exc
    if conflicts:
        raise InstallError(
            "Existing entries conflict with this installation; nothing was installed.\n"
            "Move any copies or different links aside yourself, then rerun.\n  "
            + "\n  ".join(conflicts)
        )

    # Keep identities as well as paths so a concurrently replaced entry is not
    # removed during rollback. Existing correct links are never changed.
    created: list[tuple[Path, str, int, int]] = []
    try:
        skills_dir.mkdir(parents=True, exist_ok=True)
        for name, destination, needed in entries:
            if not needed:
                continue
            target = str(sources[name])
            os.symlink(target, destination, target_is_directory=True)
            identity = destination.lstat()
            created.append((destination, target, identity.st_dev, identity.st_ino))
    except OSError as exc:
        rollback_problems: list[str] = []
        for destination, target, device, inode in reversed(created):
            try:
                identity = destination.lstat()
                if (
                    stat.S_ISLNK(identity.st_mode)
                    and (identity.st_dev, identity.st_ino) == (device, inode)
                    and os.readlink(destination) == target
                ):
                    destination.unlink()
            except FileNotFoundError:
                pass
            except OSError as rollback_exc:
                rollback_problems.append(f"{destination}: {rollback_exc}")
        message = f"Installation failed: {exc}. Rolled back links created by this attempt."
        if rollback_problems:
            message += "\nSome created links could not be removed:\n  " + "\n  ".join(rollback_problems)
        raise InstallError(message) from exc
    return entries


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=PROVIDER_DIRECTORIES, help="Skill host: Codex or Claude Code (app or CLI).")
    parser.add_argument("--skills-dir", type=Path, help="Use this installation directory instead of the provider's personal skills directory.")
    args = parser.parse_args(argv)
    skills_dir = args.skills_dir
    if skills_dir is None:
        skills_dir = Path.home() / PROVIDER_DIRECTORIES[args.provider] / "skills"
    try:
        entries = install_skills(skills_dir)
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for name, destination, created in entries:
        status = "Installed" if created else "Already installed"
        print(f"{status} {name}: {destination}")
    for name in RETIRED_SKILL_NAMES:
        old_entry = skills_dir.expanduser().absolute() / name
        if os.path.lexists(old_entry):
            print(
                f"Note: retired shortcut left untouched: {old_entry}. "
                "Use math-paper-verifier-focused instead. Move the old entry "
                "outside the skills directory to retire it while preserving local changes.",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
