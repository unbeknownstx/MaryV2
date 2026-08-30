#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

FORBIDDEN = ('.env', 'data/', '.git/', '.venv/', 'node_modules/')
REQUIRED_REPO_FILES = ('mary/core/mary.py', 'mary/runtime/application.py', 'scripts/run_release_verification.py')
TARGETED_TESTS = [
    'tests/character/test_sourcebook.py',
    'tests/character/test_evaluation.py',
    'tests/expression/test_emotion_momentum.py',
    'tests/runtime/test_state_reconciliation.py',
    'tests/runtime/test_recovery.py',
    'tests/runtime/test_root_authority_convergence.py',
    'tests/creative/test_cross_media_production.py',
    'tests/creative/test_service_registry.py',
    'tests/runtime/test_application_integrity.py',
    'tests/desktop/test_headless_windows_node_13_2.py',
    'tests/desktop/test_device_node_agent_13_2.py',
    'tests/desktop/test_ollama_task_executor_13_2.py',
    'tests/llm/test_device_ollama_provider_13_2.py',
]

def norm(rel: str) -> str:
    rel = rel.replace('\\','/')
    while rel.startswith('./'):
        rel = rel[2:]
    return rel

def backup_base() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    if root:
        return Path(root) / 'MaryV2' / 'upgrade_backups'
    return Path.home() / '.maryv2' / 'upgrade_backups'

def rollback(repo: Path, backup: Path, record: dict) -> None:
    for item in reversed(record.get('files', [])):
        rel = item['path']
        target = repo / rel
        if item['existed']:
            source = backup / 'files' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif target.exists():
            target.unlink()
    print(f'Rollback restored pre-upgrade files from: {backup}')

def run(cmd: list[str], cwd: Path) -> None:
    print('>', ' '.join(cmd))
    completed = subprocess.run(cmd, cwd=str(cwd))
    if completed.returncode:
        raise RuntimeError(f'Command failed with exit code {completed.returncode}: {cmd}')

def main() -> int:
    ap = argparse.ArgumentParser(description='Install the MaryV2 Convergence Upgrade safely.')
    ap.add_argument('--repo', default='.', help='MaryV2 repository root')
    ap.add_argument('--skip-tests', action='store_true', help='Install without post-install verifier/tests')
    ap.add_argument('--full-suite', action='store_true', help='Also run the full pytest suite')
    ap.add_argument('--keep-on-failure', action='store_true', help='Do not auto-rollback if verification fails')
    args = ap.parse_args()

    package = Path(__file__).resolve().parent
    payload = package / 'payload'
    manifest = json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
    repo = Path(args.repo).expanduser().resolve()
    for required in REQUIRED_REPO_FILES:
        if not (repo/required).is_file():
            print(f'ERROR: {repo} does not look like the MaryV2 repo (missing {required}).')
            return 2

    rels = [norm(item['path']) for item in manifest['files']]
    for rel in rels:
        low = rel.lower()
        if low == '.env' or any(low.startswith(prefix) for prefix in FORBIDDEN[1:]):
            print(f'ERROR: forbidden payload target: {rel}')
            return 3
        if not (payload/rel).is_file():
            print(f'ERROR: payload is incomplete: {rel}')
            return 3

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = backup_base() / f'convergence-{stamp}'
    (backup/'files').mkdir(parents=True, exist_ok=True)
    record = {'installed_at':stamp, 'repo':str(repo), 'package':str(package), 'files':[]}

    print(f'MaryV2 repo: {repo}')
    print(f'Backup:      {backup}')
    print(f'Files:       {len(rels)}')

    try:
        for rel in rels:
            source = payload/rel
            target = repo/rel
            existed = target.exists()
            if existed:
                b = backup/'files'/rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target,b)
            record['files'].append({'path':rel,'existed':bool(existed)})
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source,target)
        (backup/'install_record.json').write_text(json.dumps(record,indent=2),encoding='utf-8')

        if not args.skip_tests:
            py = sys.executable
            run([py,'-m','scripts.verify_maryv2_convergence'],repo)
            existing_tests=[x for x in TARGETED_TESTS if (repo/x).is_file()]
            run([py,'-m','pytest','-q',*existing_tests],repo)
            if args.full_suite:
                run([py,'-m','pytest','tests','-q'],repo)
    except Exception as exc:
        print(f'INSTALL/VERIFY ERROR: {exc}')
        if args.keep_on_failure:
            print(f'Changes were kept. Backup is at: {backup}')
        else:
            print('Verification failed; restoring the pre-upgrade files automatically...')
            rollback(repo,backup,record)
        return 1

    print('\nMARYV2 CONVERGENCE UPGRADE INSTALLED')
    print(f'Backup retained at: {backup}')
    print('Your .env, data/, memories, secrets, and media assets were not part of this payload.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
