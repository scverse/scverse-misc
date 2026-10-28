#!/usr/bin/env -S uv run --script
# SPDX-License-Identifier: MPL-2.0
# /// script
# requires-python = ">=3.12"
# dependencies = ["wenmode"]
# ///
"""Check that a PR’s changelog entry is in the section its conventional-commit title implies.

The entry is a list item under `## [Unreleased]` › `### <Section>` that ends with the PR number,
e.g. `- Some fix (#67)`.
PR titles with types that don’t map to a section (`ci:`, `docs:`, …) need no entry,
but every PR needs the changelog to keep its `## [Unreleased]` section,
and every `##` heading to be a link with a definition, e.g. `[0.1.0]: https://…`.

Usage
-----
    uv run scripts/check_changelog.py --pr 67 --title 'fix: make logo fill sidebar'
"""

from __future__ import annotations

import re
from argparse import ArgumentParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from wenmode import Wenmode
from wenmode.nodes import Heading, Link, List, ListItem, Literal, Paragraph, Parent, Text

if TYPE_CHECKING:
    from wenmode.nodes import Node

SECTIONS = {"feat": "Added", "fix": "Fixed", "perf": "Changed"}
UNRELEASED = "Unreleased"


class ChangelogError(SystemExit):
    """A problem with the changelog, exiting with a GitHub error annotation when uncaught."""

    def __init__(self, msg: str, *, file: Path, line: int | None = None) -> None:
        self.msg = msg
        self.line = line
        loc = f"file={file}{f',line={line}' if line else ''}"
        super().__init__(f"::error {loc}::{msg}")


@dataclass(frozen=True)
class Entry:
    """A changelog list item."""

    line: int
    pr: int | None


@dataclass
class Changelog:
    """A parsed changelog: version › section › entries."""

    path: Path
    versions: dict[str, dict[str, list[Entry]]] = field(default_factory=dict)

    @classmethod
    def parse(cls, path: Path) -> Changelog:
        """Parse the changelog, raising :class:`ChangelogError` if it is malformed."""
        text = path.read_text()
        changelog = cls(path)
        sections: dict[str, list[Entry]] | None = None
        entries: list[Entry] | None = None
        for node in Wenmode(positions=True).parse(text).children:
            match node:
                case Heading(depth=2, children=[Link() as link]):
                    sections = changelog.versions.setdefault(_text(link), {})
                    entries = None
                case Heading(depth=2):
                    msg = f"“## {_text(node)}” isn’t a link; add a “[<version>]: <url>” definition"
                    raise ChangelogError(msg, file=path, line=_line(text, node))
                case Heading(depth=3) if sections is not None:
                    entries = sections.setdefault(_text(node), [])
                case List(children=items) if entries is not None:
                    entries.extend(_parse_entry(text, path, item) for item in items)
        if UNRELEASED not in changelog.versions:
            msg = "No “## [Unreleased]” section"
            raise ChangelogError(msg, file=path)
        return changelog

    def check(self, pr: int, title: str) -> None:
        """Raise :class:`ChangelogError` unless the entry for `pr` is in the section `title` implies."""
        if not (m := re.match(r"(\w+)(?:\([^)]*\))?!?:", title)) or not (want := SECTIONS.get(m[1])):
            return
        found = [
            (entry, version, section)
            for version, sections in self.versions.items()
            for section, entries in sections.items()
            for entry in entries
            if entry.pr == pr
        ]
        if any(version == UNRELEASED and section == want for _, version, section in found):
            return
        if not found:
            msg = f"No list item ending in “(#{pr})”; “{title}” needs one under “## [Unreleased]” › “### {want}”"
            raise ChangelogError(msg, file=self.path)
        entry, version, section = found[0]
        msg = f"Entry for #{pr} is under “## [{version}]” › “### {section}”, but “{title}” needs “## [Unreleased]” › “### {want}”"
        raise ChangelogError(msg, file=self.path, line=entry.line)


def _text(node: Node) -> str:
    match node:
        case Literal(value=value):
            return value
        case Parent(children=children):
            return "".join(map(_text, children))
    return ""


def _line(text: str, node: Node) -> int:
    assert node.position is not None
    return text.count("\n", 0, node.position.start) + 1


def _parse_entry(text: str, path: Path, item: Node) -> Entry:
    line = _line(text, item)
    match item:
        case ListItem(children=[Paragraph(children=[*rest, Text(value=value)]), *_]):
            if m := re.search(r"\(#(\d+)\)$", value):
                if not rest and value == m[0]:
                    msg = f"Entry “{value}” has no description"
                    raise ChangelogError(msg, file=path, line=line)
                return Entry(line, int(m[1]))
    return Entry(line, None)


def main() -> None:
    """Exit with a GitHub error annotation if the changelog is malformed or the entry is missing or misplaced."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = parser.parse_args()

    Changelog.parse(args.changelog).check(args.pr, args.title)


if __name__ == "__main__":
    main()
