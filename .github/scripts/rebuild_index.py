import sys
import os
from datetime import datetime

repo_root = os.environ.get('GITHUB_WORKSPACE', '.')
readme_path = os.path.join(repo_root, 'README.md')
raw_path = '/tmp/releases_raw.txt'

groups = {}
with open(raw_path, 'r') as f:
    for line in f:
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|', 2)
        if len(parts) != 3:
            continue
        tag, date_str, name = parts
        name = name or tag
        image = name.rsplit(' ', 1)[0].strip() if ' ' in name else name.strip()
        version = tag.lstrip('v')
        try:
            date_fmt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        except Exception:
            date_fmt = date_str[:10]
        link = f"[View](../../releases/tag/{tag})"
        groups.setdefault(image, []).append((version, date_fmt, link))

sorted_groups = sorted(groups.items(), key=lambda x: x[0].lower())
for img, entries in sorted_groups:
    entries.sort(key=lambda x: x[1], reverse=True)

lines = [
    "| 镜像 | 最新版本 | 更新时间 | Release |",
    "|------|---------|---------|--------|"
]
for img, entries in sorted_groups:
    for ver, date, link in entries:
        lines.append(f"| {img} | {ver} | {date} | {link} |")

table_md = '\n'.join(lines) + '\n'

content = open(readme_path, 'r').read()
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
open(readme_path, 'w').write(result)
print(f'Successfully updated {readme_path}')
