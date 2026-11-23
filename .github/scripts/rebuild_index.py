import sys
import os
import json
import re
from datetime import datetime

repo_root = os.environ.get('GITHUB_WORKSPACE', '.')
readme_path = os.path.join(repo_root, 'README.md')
raw_path = '/tmp/releases_raw.json'

# 1) 工作流正文里可选的隐藏标识（以后加就自动生效）
MARKER = re.compile(r'<!--\s*mirror:\s*(\S+)\s*-->')


def load_releases(path):
    """支持单个 JSON 数组，或每行一个 JSON 对象（JSONL）。"""
    text = open(path, encoding='utf-8').read().strip()
    if not text:
        return []
    if text.startswith('['):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def identity(rel):
    """确定这条 release 属于哪个镜像：优先稳定标识，最后退回名称。"""
    name = (rel.get('name') or rel.get('tagName') or '').strip()
    body = rel.get('body') or ''

    m = MARKER.search(body)
    if m:
        return m.group(1).strip(), 'marker'

    if ' ' in name:
        return name.rsplit(' ', 1)[0].strip(), 'name'
    return name.strip(), 'name'


releases = load_releases(raw_path)

latest = {}
label = {}
conflict = []

for rel in releases:
    tag = (rel.get('tagName') or '').strip()
    if not tag:
        continue

    key, how = identity(rel)
    if not key:
        continue

    name = (rel.get('name') or tag).strip()
    if how == 'marker':
        # 标识里的镜像是规范写法，直接用它当显示名
        display = key
    else:
        display = name.rsplit(' ', 1)[0].strip() if ' ' in name else name.strip()

    version = tag[1:] if tag.startswith('v') else tag

    date_str = rel.get('publishedAt') or ''
    try:
        date_fmt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except Exception:
        date_fmt = date_str[:10]

    link = f"[View](../../releases/tag/{tag})"

    if key not in latest:
        latest[key] = (version, date_fmt, link)
        label[key] = display
        continue

    # 同一天发布时用版本号兜底比较，避免顺序抖动
    if (date_fmt, version) > (latest[key][1], latest[key][0]):
        latest[key] = (version, date_fmt, link)
        label[key] = display
    elif display and label.get(key) != display:
        conflict.append((tag, display, label.get(key)))

rows = []
for key, (ver, date, link) in latest.items():
    rows.append((label.get(key) or key, ver, date, link))

rows.sort(key=lambda r: r[0].lower())

lines = [
    "| 镜像 | 最新版本 | 更新时间 | Release |",
    "|------|---------|---------|--------|"
]
for img, ver, date, link in rows:
    lines.append(f"| {img} | {ver} | {date} | {link} |")

table_md = '\n'.join(lines) + '\n'

content = open(readme_path, encoding='utf-8').read()
start = '<!-- AUTO-INDEX-START -->'
end = '<!-- AUTO-INDEX-END -->'
if start not in content or end not in content:
    print(f'Error: Missing anchor comments in {readme_path}', file=sys.stderr)
    print('Please ensure README.md contains both <!-- AUTO-INDEX-START --> and <!-- AUTO-INDEX-END -->', file=sys.stderr)
    sys.exit(1)

result = (
    content[:content.index(start) + len(start)]
    + '\n' + table_md + '\n'
    + content[content.index(end):]
)
open(readme_path, 'w', encoding='utf-8').write(result)

print(f'Successfully updated {readme_path} ({len(rows)} images)')
for tag, display, kept in conflict:
    print(f'::warning::{tag} 的显示名 "{display}" 与该镜像既有显示名 "{kept}" 不同，已沿用最新一条。')
