import json
import os
import re
import subprocess
import sys

REPO = os.environ["GITHUB_REPOSITORY"]
KEEP = int(os.environ.get("KEEP", "5"))
RAW = os.environ.get("RELEASES_JSON", "/tmp/releases_raw.json")

IMAGE_LINE = re.compile(r'- \*\*Image\*\*:\s*`([^`]+)`')
VARIANT_WORD = re.compile(r'\s+(lite|slim|alpine)\s*$', re.I)


def load(path):
    text = open(path, encoding="utf-8").read().strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def repo_name(rel):
    """与 rebuild_index.py 同一口径：优先正文里的拉取引用，其次名称前缀。"""
    body = rel.get("body") or ""
    m = IMAGE_LINE.search(body)
    if m:
        ref = re.sub(r"^ghcr\.io/", "", m.group(1).strip())
        return ref.rsplit(":", 1)[0] if ":" in ref else ref

    name = (rel.get("name") or rel.get("tagName") or "").strip()
    prefix = name.rsplit(" ", 1)[0].strip() if " " in name else name
    prefix = re.sub(r"^ghcr\.io/", "", prefix)
    return VARIANT_WORD.sub("", prefix)


def variant_of(rel):
    tag = (rel.get("tagName") or "").strip()
    for v in ("lite", "slim", "alpine"):
        if tag.endswith("-" + v):
            return v
    return ""


def gh_api(args):
    p = subprocess.run(["gh", "api"] + args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


releases = load(RAW)
groups = {}
for rel in releases:
    rid = rel.get("id")
    tag = (rel.get("tagName") or "").strip()
    if not rid or not tag:
        continue
    key = repo_name(rel) + ("-" + variant_of(rel) if variant_of(rel) else "")
    groups.setdefault(key, []).append(rel)

# 只在"分组内确实超出保留数"时才动手，且始终保留发布日期最新的 KEEP 个
victims = []
for key, items in groups.items():
    items.sort(key=lambda x: (x.get("publishedAt") or "", x.get("tagName") or ""), reverse=True)
    victims += items[KEEP:]

if not victims:
    print(f"每个分组都不超过 {KEEP} 个，无需清理。")
    sys.exit(0)

print(f"将删除 {len(victims)} 个超出保留数的发布物（每组保留最新 {KEEP} 个）")
failed = 0
for rel in victims:
    rid, tag = rel["id"], rel["tagName"]
    rc, out, err = gh_api(["-X", "DELETE", f"repos/{REPO}/releases/{rid}"])
    if rc != 0:
        print(f"::warning::删除 Release {tag} 失败：{err.strip()[:200]}")
        failed += 1
        continue
    rc, out, err = gh_api(["-X", "DELETE", f"repos/{REPO}/git/refs/tags/{tag}"])
    if rc != 0 and "Reference does not exist" not in err and "422" not in err:
        print(f"::warning::标签 {tag} 删除失败（Release 已删）：{err.strip()[:200]}")
    print(f"已删除 {tag}")

print(f"完成：删除 {len(victims) - failed} 个，失败 {failed} 个")
sys.exit(1 if failed else 0)
