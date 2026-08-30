#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser(description='Rollback a MaryV2 Convergence Upgrade backup.')
    ap.add_argument('--backup', required=True)
    ap.add_argument('--repo', default=None)
    args=ap.parse_args()
    backup=Path(args.backup).expanduser().resolve()
    record=json.loads((backup/'install_record.json').read_text(encoding='utf-8'))
    repo=Path(args.repo or record['repo']).expanduser().resolve()
    print(f'Restoring: {repo}')
    print(f'From:      {backup}')
    for item in reversed(record['files']):
        rel=item['path']; target=repo/rel
        if item['existed']:
            src=backup/'files'/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,target)
        elif target.exists():
            target.unlink()
    print('Rollback complete.')
    return 0
if __name__ == '__main__': raise SystemExit(main())
