import sys
import os
import json
import re
from datetime import datetime

repo_root = os.environ.get('GITHUB_WORKSPACE', '.')
readme_path = os.path.join(repo_root, 'README.md')
raw_path = os.environ.get('RELEASES_JSON', '/tmp/releases_raw.json')

MARKER = re.compile(r'<!--\s*mirror:\s*(\S+)\s*-->')
IMAGE_LINE = re.compile(r'- \*\*Image\*\*:\s*`([^`]+)`')
LITE_WORD = re.compile(r'\s+lite\s*$', re.I)

# 只有这些后缀才算"镜像变体"并单独成行，避免把 2026.7.1-2 这类版本号误判
KNOWN_VARIANTS = ('lite', 'slim', 'alpine')


def load_releases(path):
    text = open(path, encoding='utf-8').read().strip()
    if not text:
        return []
    if text.startswith('['):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def repo_name(rel):
    body = rel.get('body') or ''
    m = IMAGE_LINE.search(body)
    if m:
        ref = m.group(1).strip()
        return ref.rsplit(':', 1)[0] if ':' in ref else ref

    m = MARKER.search(body)
    if m:
        return m.group(1).strip()

    name = (rel.get('name') or rel.get('tagName') or '').strip()
    prefix = name.rsplit(' ', 1)[0].strip() if ' ' in name else name
    return LITE_WORD.sub('', prefix)


def variant_of(version):
    if '-' not in version:
        return ''
    last = version.rsplit('-', 1)[1].strip().lower()
    if last in KNOWN_VARIANTS and last != version.lower():
        return last
    return ''


releases = load_releases(raw_path)

latest = {}
for rel in releases:
    tag = (rel.get('tagName') or '').strip()
    if not tag:
        continue
    repo = repo_name(rel)
    if not repo:
        continue

    version = tag[1:] if tag.startswith('v') else tag
    variant = variant_of(version)
    key = repo + ('-' + variant if variant else '')

    date_str = rel.get('publishedAt') or ''
    try:
        date_fmt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except Exception:
        date_fmt = date_str[:10]

    link = f"[View](../../releases/tag/{tag})"

    if key not in latest:
        latest[key] = (repo, version, date_fmt, link)
    elif (date_fmt, version) > (latest[key][2], latest[key][1]):
        latest[key] = (repo, version, date_fmt, link)

rows = list(latest.values())
rows.sort(key=lambda r: (r[0].lower(), r[1]))

lines = [
    "| 镜像 | 标签 | 更新时间 | Release |",
    "|------|------|---------|--------|"
]
for img, ver, date, link in rows:
    lines.append(f"| {img} | {ver} | {date} | {link} |")

table_md = '\n'.join(lines) + '\n'

content = open(readme_path, encoding='utf-8').read()
start = '<!-- AUTO-INDEX-START -->'
end = '<!-- AUTO-INDEX-END -->'
if start not in content or end not in content:
    print(f'Error: Missing anchor comments in {readme_path}', file=sys.stderr)
    sys.exit(1)

result = (
    content[:content.index(start) + len(start)]
    + '\n' + table_md + '\n'
    + content[content.index(end):]
)
open(readme_path, 'w', encoding='utf-8').write(result)

print(f'Successfully updated {readme_path} ({len(rows)} images)')
for img, ver, date, link in rows:
    print(f'  {img}:{ver}')
