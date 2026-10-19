#!/usr/bin/env python3
"""Rewrite UI copy in the working tree with the Chinese overlay, for the CI build only.

The rewrite is deliberately confined to the runner workspace: nothing is committed, so merging
upstream never conflicts with the overlay. Sources are only touched where a table row matches
the literal's normalized form (`"${n} files"` -> key `"{0} files"`), which keeps the change
mechanical and reviewable.

Interpolations are restored from the source as it stands at build time, so a renamed variable
upstream still lands in the right place inside the Chinese sentence.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_zh_table import (  # noqa: E402
    interpolation_bodies,
    is_display_copy,
    is_safe_context,
    kotlin_strings,
    literal_chains,
    load_table,
    normalize,
    scan_repo,
)

PLACEHOLDER = re.compile(r"\{(\d+)\}")



def escape_for_kotlin(text: str) -> str:
    """Re-escape what the translation needs so the injected literal still compiles.

    Newlines are rewritten last and onto a backslash-n escape: a raw newline inside a single-line
    literal closes the string early and breaks the build.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return escaped.replace("\r\n", "\\n").replace("\n", "\\n")


def render(translation: str, bodies: list[str]) -> str:
    """Fill a translation's {n} slots with the interpolations the source currently uses.

    Only the translation's own text is escaped. An interpolation is copied verbatim, so its
    `$`, quotes and nested string literals keep working — escaping the joined result would
    turn `"${count} 项"` into the literal text `${count}`.
    """
    out = []
    cursor = 0
    for match in PLACEHOLDER.finditer(translation):
        out.append(escape_for_kotlin(translation[cursor:match.start()]))
        slot = int(match.group(1))
        if slot >= len(bodies):
            raise ValueError(f"译文引用了不存在的占位符 {{{slot}}}（源码只有 {len(bodies)} 个插值）")
        out.append(bodies[slot])
        cursor = match.end()
    out.append(escape_for_kotlin(translation[cursor:]))
    return "".join(out)


def apply_to_text(text: str, table: dict[str, str]) -> tuple[str, int, int, list[str]]:
    spans = list(kotlin_strings(text))
    if not spans:
        return text, 0, 0, []

    pieces = []
    cursor = 0
    replaced = 0
    skipped = 0
    problems: list[str] = []
    for chain in literal_chains(text, spans):
        first_start, first_end = chain[0]
        last_end = chain[-1][1]
        # Only plain double-quoted literals are rewritten; touching a `"""` block or a char
        # literal would need different quoting and is not worth guessing at.
        if text[first_start - 1] != '"' or text[last_end] != '"':
            continue
        start = first_start - 1
        end = last_end + 1
        merged = "".join(text[s:e] for s, e in chain)
        key = normalize(merged).strip()
        translation = table.get(key)
        if translation is None:
            continue
        context = text[max(0, start - 161):start - 1]
        # Same guard the extractor used: this literal must be shown, not compared, and its
        # surroundings must still look like a display field.
        if not is_display_copy(merged, key, context) or not is_safe_context(text, start, end):
            skipped += 1
            continue
        bodies = interpolation_bodies(merged)
        used = {int(slot) for slot in PLACEHOLDER.findall(translation)}
        # A translation may reorder placeholders for Chinese word order, but dropping one
        # silently deletes live data from the UI, which no build check downstream would catch.
        if used != set(range(len(bodies))):
            problems.append(f"{key!r}: 占位符不匹配（源码 {len(bodies)} 个，译文用了 {sorted(used)}）")
            continue
        rendered = render(translation, bodies)
        pieces.append(text[cursor:start])
        pieces.append(f'"{rendered}"')
        cursor = end
        replaced += 1
    pieces.append(text[cursor:])
    return "".join(pieces), replaced, skipped, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="repository root")
    parser.add_argument("--table", default="scripts/ci-zh-strings.csv")
    parser.add_argument("--check", action="store_true", help="report without writing")
    parser.add_argument("--summary", metavar="PATH", help="append a one-line summary to this file")
    parser.add_argument("--min", type=int, default=0,
                        help="fail when fewer than N literals were rewritten (guards a silent no-op)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    table = load_table(repo / args.table)
    if not table:
        print(f"::warning::对照表为空或不存在：{args.table}", file=sys.stderr)
        return 0

    total = 0
    skipped = 0
    touched: list[str] = []
    problems: list[str] = []
    for path, text in scan_repo(repo):
        updated, count, held, issues = apply_to_text(text, table)
        skipped += held
        problems.extend(f"{path.relative_to(repo)}: {issue}" for issue in issues)
        if count == 0:
            continue
        total += count
        touched.append(f"{path.relative_to(repo)}（{count} 处）")
        if not args.check and updated != text:
            path.write_text(updated, encoding="utf-8")

    print(f"注入文案：{total} 处，涉及 {len(touched)} 个文件（对照表 {len(table)} 条）")
    if skipped:
        print(f"跳过：{skipped} 处（命中了对照表，但该处是文本比较/非展示上下文，保持英文）")
    if args.check:
        print("（--check：未写入）")
    if problems:
        print("\n需要人工处理：", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
    if total < args.min:
        print(f"::error::只注入了 {total} 处（要求至少 {args.min}）—— 对照表或扫描范围失效了",
              file=sys.stderr)
        return 1
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as handle:
            handle.write(f"中文覆盖：{total} 处 / {len(touched)} 文件；对照表 {len(table)} 条\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
