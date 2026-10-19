#!/usr/bin/env python3
"""Shared pieces for the Chinese overlay: Kotlin literal scanning, key normalization, table IO.

Kept separate from the two commands so the extractor and the injector cannot drift apart on
what a "key" is; a mismatch there would silently translate nothing at all.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

INTERP_START = re.compile(r"\$\{|\$[A-Za-z_]")

SCAN_ROOTS = (
    "feature/*/presentation/src/main",
    "feature/*/ui/src/main",
    "core/ui/src/main",
    "app/src/main",
)
SKIP_DIRECTORIES = {"/build/", "/.gradle/", "/.git/", "/test/", "/androidTest/", "/generated/"}


def skip_interpolation(text: str, index: int) -> int:
    """Return the offset just past the interpolation starting at text[index] == '$'.

    The expression may contain string literals and nested braces, so quoted runs are skipped;
    a bare brace counter would stop early on `"a${join(" and ")}b"`.
    """
    length = len(text)
    if index + 1 < length and text[index + 1] == "{":
        depth = 0
        cursor = index + 1
        while cursor < length:
            char = text[cursor]
            if char == '"':
                cursor += 1
                while cursor < length:
                    if text[cursor] == "\\":
                        cursor += 2
                        continue
                    if text[cursor] == '"':
                        cursor += 1
                        break
                    cursor += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return cursor + 1
            cursor += 1
        return length
    cursor = index + 1
    while cursor < length and (text[cursor].isalnum() or text[cursor] == "_"):
        cursor += 1
    return cursor


def kotlin_strings(text: str):
    """Yield (content_start, content_end) for every Kotlin string literal, skipping comments.

    Offsets cover the literal body only, without the quotes, so a caller can rewrite the run
    in place and leave the surrounding expression untouched.
    """
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            newline = text.find("\n", index)
            index = length if newline < 0 else newline + 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        if char == "'":
            index += 1
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "'":
                    index += 1
                    break
                index += 1
            continue
        if text.startswith('"""', index):
            end = text.find('"""', index + 3)
            if end < 0:
                return
            yield index + 3, end
            index = end + 3
            continue
        if char == '"':
            cursor = index + 1
            start = cursor
            while cursor < length:
                current = text[cursor]
                if current == "\\":
                    cursor += 2
                    continue
                if current == "$":
                    cursor = skip_interpolation(text, cursor)
                    continue
                if current == '"':
                    break
                cursor += 1
            yield start, cursor
            index = cursor + 1
            continue
        index += 1


def normalize(literal: str) -> str:
    """Replace each interpolation with {n} so the key survives local variable renames."""
    out = []
    index = 0
    slot = 0
    while index < len(literal):
        match = INTERP_START.search(literal, index)
        if match is None:
            out.append(literal[index:])
            break
        out.append(literal[index:match.start()])
        index = skip_interpolation(literal, match.start())
        out.append("{%d}" % slot)
        slot += 1
    return "".join(out)


def interpolation_bodies(literal: str) -> list[str]:
    """Return each interpolation exactly as written, in placeholder order."""
    bodies = []
    index = 0
    while index < len(literal):
        match = INTERP_START.search(literal, index)
        if match is None:
            break
        end = skip_interpolation(literal, match.start())
        bodies.append(literal[match.start():end])
        index = end
    return bodies


def scan_repo(repo: Path):
    """Yield (path, text) for every Kotlin file the overlay may touch."""
    for root in SCAN_ROOTS:
        for path in sorted(repo.glob(root + "/**/*.kt")):
            raw = str(path).replace("\\", "/")
            if any(token in "/" + raw for token in SKIP_DIRECTORIES):
                continue
            yield path, path.read_text(encoding="utf-8", errors="ignore")


WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

TECHNICAL = re.compile(
    r"""^(
        [a-z0-9_.]+/[a-z0-9_.]+ |          # paths and mime types
        (?:[a-z_]+\d*\.)+[A-Za-z_]+ |      # dotted identifiers such as ro.boot.*
        [A-Za-z0-9_]+\([^)]*\) |           # call-shaped tokens
        0[xX][0-9a-fA-F]+ |
        [0-9.]+(?:dp|sp|px|ms|ns|KB|MB|GB)? |
        [A-Za-z0-9_-]+:[A-Za-z0-9_./-]+ |  # uri schemes and key:value tokens
        [a-z0-9_]+(?:_[a-z0-9]+)+ |        # snake_case identifiers
        [A-Za-z]+[0-9]+[A-Za-z0-9]*        # identifiers with digits glued on
    )$""",
    re.VERBOSE,
)

# A string is UI copy when it is prose or sits in a field the presentation layer renders as
# it is. The list mirrors the card and export models.
COPY_FIELD = re.compile(
    r"""(?:^|[\s(,{])(?:
        title|subtitle|verdict|summary|headline|label|detail|details|text|message|
        description|value|placeholder|hint|caption|footnote|badge|note|
        contentDescription|statusText|captionText|emptyText
    )\s*=\s*$""",
    re.VERBOSE,
)

# A single word is only copy when the code says so: CRITICAL("Critical") carries a display
# label, while a lone lower-case word is an animation label or test tag.
ENUM_ENTRY = re.compile(r"^[A-Z][A-Z0-9_]*\s*\(\s*$")


def is_display_copy(literal: str, key: str, context: str) -> bool:
    words = WORD.findall(re.sub(r"\{\d+\}", " ", key))
    if not words:
        return False
    stripped = literal.strip()
    if TECHNICAL.match(stripped):
        return False
    # Regexes, path globs, URLs and Maven coordinates share these separators and are never prose.
    if "\\" in literal or "://" in literal or "[" in literal:
        return False
    if re.search(r"[A-Za-z0-9_][\w.\-]*:[\w.\-]+", stripped) and " " not in stripped:
        return False
    if "(" in stripped and ")" not in stripped:
        return False
    # A date/time pattern reads as words but is not copy (for example yyyyMMdd_HHmmss).
    if re.fullmatch(r"[yMdHhmsSEaDdZzT:_/\-. ]+", stripped):
        return False
    # Export section headings are upper case by design and are not part of this overlay.
    if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return False
    if len(words) == 1 and stripped[:1].islower():
        return False
    # key=value pairs report probe state, not prose.
    if "=" in stripped and " " not in stripped:
        return False
    if len(words) >= 2:
        return True
    return bool(COPY_FIELD.search(context) or ENUM_ENTRY.search(context))


COMPARISON_BEFORE = re.compile(r"(?:==|!=|===|!==)\s*$")
COMPARISON_AFTER = re.compile(r"^\s*(?:==|!=|===|!==|->|,\s*\"[^\"]*\"\s*->)")


def is_safe_context(text: str, start: int, end: int) -> bool:
    """Reject literals the code compares against instead of showing.

    A translated literal that also serves as a wire value, a status key or a `when` branch
    would silently stop matching anything, so the overlay leaves those alone even when the
    same English also appears as copy elsewhere.
    """
    if COMPARISON_BEFORE.search(text[max(0, start - 8):start - 1]):
        return False
    if COMPARISON_AFTER.match(text[end + 1:end + 40]):
        return False
    return True


def load_table(path: Path) -> dict[str, str]:
    """Read the overlay table: `en,zh,note` rows, empty `zh` meaning "not translated yet".

    A literal `\\n` stands for a newline in both columns, so a multi-line source literal still
    occupies exactly one row and `git diff` shows which entry changed. Parsing uses the standard
    library's csv module rather than hand-rolled splitting: source copy contains commas, colons
    and quotes, and RFC 4180 quoting is exactly what csv already gets right.
    """
    table: dict[str, str] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 2 or not row[0].strip():
                continue
            if row[0] == "en":
                continue
            key, value = row[0], row[1]
            if not value.strip():
                continue
            table[key.replace("\\n", "\n")] = value.replace("\\n", "\n")
    return table
