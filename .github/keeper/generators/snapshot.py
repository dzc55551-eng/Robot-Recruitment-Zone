# -*- coding: utf-8 -*-
"""运行状态快照：写入仓库内的状态文件，记录真实观测值。

每次运行都会刷新 last_check_at 与 checks_today —— 这两个字段反映的是
当天实际执行了几次巡检，不是人为制造的变化。
"""

import json
import re
import urllib.error
import urllib.request

GENERATOR = "snapshot"
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def _api(path, token):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "github-repo-keeper"},
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def _collect_positions(repo_path):
    items = []
    for path in sorted(repo_path.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = TITLE_RE.search(text)
        items.append({
            "file": path.name,
            "title": match.group(1) if match else path.stem,
        })
    return items


def run(cfg, repo_path, token, now):
    status_path = repo_path / cfg.get("snapshot_path", "positions/status.json")
    old = {}
    if status_path.exists():
        try:
            old = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}

    positions = _collect_positions(repo_path)
    archived_dir = repo_path / "archive"
    archived = list(archived_dir.glob("*.md")) if archived_dir.is_dir() else []

    stamp = now.isoformat(timespec="seconds")
    today = now.strftime("%Y-%m-%d")
    if old.get("date") == today:
        first_check = old.get("first_check_at") or stamp
        checks = int(old.get("checks_today") or 0) + 1
    else:
        first_check = stamp
        checks = 1

    payload = {
        "date": today,
        "first_check_at": first_check,
        "last_check_at": stamp,
        "checks_today": checks,
        "positions_open": len(positions),
        "positions_archived": len(archived),
        "titles": [p["title"] for p in positions],
        "generator": GENERATOR,
    }

    info = _api("/repos/%s/%s" % (cfg["owner"], cfg["repo"]), token)
    if info:
        payload["upstream"] = {
            "stars": info.get("stargazers_count", 0),
            "forks": info.get("forks_count", 0),
            "open_issues": info.get("open_issues_count", 0),
        }

    status_path.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    changed = (not status_path.exists()) or status_path.read_text(encoding="utf-8") != new_text
    if changed:
        status_path.write_text(new_text, encoding="utf-8")

    return {
        "name": GENERATOR,
        "changed": changed,
        "positions_open": len(positions),
        "checks_today": checks,
        "path": str(status_path.relative_to(repo_path)).replace("\\", "/"),
    }
