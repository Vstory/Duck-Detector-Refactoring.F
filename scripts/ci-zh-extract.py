#!/usr/bin/env python3
"""List the user-facing strings the Chinese overlay could translate, and report drift.

The overlay lives in `scripts/ci-zh-strings.csv` and is injected while the CI builds, so the
repository stays byte-identical to upstream. This command is the read side:

* missing - source copy with no row in the table (the overlay leaves it English).
* stale   - a row whose English no longer appears anywhere in the source, which is what an
            upstream reword looks like.

Run it after every merge from upstream.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_zh_table import (  # noqa: E402
    is_display_copy,
    kotlin_strings,
    load_table,
    normalize,
    scan_repo,
)


@dataclass(frozen=True)
class Candidate:
    module: str
    path: str
    line: int
    key: str


def collect(repo: Path) -> dict[str, Candidate]:
    candidates: dict[str, Candidate] = {}
    for path, text in scan_repo(repo):
        relative = str(path.relative_to(repo))
        parts = path.relative_to(repo).parts
        module = parts[1] if parts[0] == "feature" else parts[0]
        for start, end in kotlin_strings(text):
            literal = text[start:end]
            if not literal.strip():
                continue
            key = normalize(literal).strip()
            if key in candidates:
                continue
            # The offset sits just past the opening quote; step back one so the assignment
            # context ("title = ") stays visible to the field check.
            context = text[max(0, start - 161):start - 1]
            if not is_display_copy(literal, key, context):
                continue
            candidates[key] = Candidate(module, relative, text.count("\n", 0, start) + 1, key)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="repository root")
    parser.add_argument("--table", default="scripts/ci-zh-strings.csv")
    parser.add_argument("--json", action="store_true", help="print the missing list as JSON")
    parser.add_argument("--write-missing", metavar="PATH", help="append empty rows for review")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    candidates = collect(repo)
    table = load_table(repo / args.table)

    missing = {k: c for k, c in candidates.items() if k not in table}
    stale = sorted(k for k in table if k not in candidates)

    if args.json:
        print(json.dumps(
            [
                {"key": c.key, "module": c.module, "path": c.path, "line": c.line}
                for c in sorted(missing.values(), key=lambda c: (c.module, c.path, c.line))
            ],
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    by_module: dict[str, int] = {}
    for candidate in missing.values():
        by_module[candidate.module] = by_module.get(candidate.module, 0) + 1

    print(f"可翻译文案：{len(candidates)}（对照表已覆盖 {len(candidates) - len(missing)}）")
    print(f"未覆盖：{len(missing)}    失效条目：{len(stale)}")
    if by_module:
        print("\n未覆盖分布：")
        for module, count in sorted(by_module.items(), key=lambda kv: -kv[1]):
            print(f"  {module:20s} {count:5d}")

    if stale:
        print("\n失效条目（源码里已找不到这些英文，多半是上游改了措辞）：")
        for key in stale:
            print(f"  {key[:110]}")

    if args.write_missing:
        target = Path(args.write_missing)
        rows = [f'"{key}": ""' for key in sorted(missing, key=lambda k: candidate_order(missing[k]))]
        header = "" if target.exists() else "en,zh,note\n"
        target.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
        print(f"\n已写入待翻译清单：{target}（{len(rows)} 行）")

    return 1 if args.fail_on_missing and missing else 0


def candidate_order(candidate: Candidate):
    return (candidate.module, candidate.path, candidate.line)


if __name__ == "__main__":
    sys.exit(main())
