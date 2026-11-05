# -*- coding: utf-8 -*-
"""索引同步：把根目录下的岗位文件与 README 的在招列表对齐。

只补缺失项，不删除、不重排 —— 已下线的岗位应由人工移入 archive，
脚本不替人做这个判断。
"""

import re

GENERATOR = "sync_index"
SECTION_KEY = "在招岗位列表"
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
CITY_RE = re.compile(r"工作地点[：:]\s*([^\s｜|、，,]+)")
LIST_RE = re.compile(r"^\s*[-*]\s+\[")
LINK_RE = re.compile(r"\]\(\./([^)]+\.md)\)")


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _section_bounds(lines):
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("## ") and SECTION_KEY in line:
            start = idx
            break
    if start is None:
        return None, None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return start, end


def _entry_for(path):
    text = _read(path)
    title_match = TITLE_RE.search(text)
    title = title_match.group(1) if title_match else path.stem
    title = title.replace("[", "").replace("]", "")
    city_match = CITY_RE.search(text)
    city = city_match.group(1).strip("()（）") if city_match else ""
    label = "%s(%s)" % (title, city) if city else title
    return "- [%s](./%s)" % (label, path.name)


def run(cfg, repo_path, token, now):
    readme = repo_path / "README.md"
    if not readme.exists():
        return {"name": GENERATOR, "changed": False, "reason": "README 不存在"}

    lines = _read(readme).split("\n")
    start, end = _section_bounds(lines)
    if start is None:
        return {"name": GENERATOR, "changed": False, "reason": "README 中没有找到「%s」区块" % SECTION_KEY}

    block = lines[start:end]
    indexed = set()
    for line in block:
        for name in LINK_RE.findall(line):
            indexed.add(name)

    candidates = [
        p for p in sorted(repo_path.glob("*.md"))
        if p.name.lower() != "readme.md"
    ]
    missing = [p for p in candidates if p.name not in indexed]
    orphaned = sorted(name for name in indexed if not (repo_path / name).exists())

    if not missing:
        return {"name": GENERATOR, "changed": False, "indexed": len(indexed), "orphaned": orphaned}

    insert_at = None
    for idx in range(len(block) - 1, -1, -1):
        if LIST_RE.match(block[idx]):
            insert_at = idx + 1
            break
    if insert_at is None:
        insert_at = min(2, len(block))

    new_lines = [_entry_for(p) for p in missing]
    block[insert_at:insert_at] = new_lines
    lines[start:end] = block
    readme.write_text("\n".join(lines), encoding="utf-8")

    return {
        "name": GENERATOR,
        "changed": True,
        "added": [p.name for p in missing],
        "orphaned": orphaned,
    }
