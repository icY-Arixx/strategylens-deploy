"""Source-only allowlist. Never package local credentials, DBs, environments or archives."""
import zipfile
import hashlib
import json
import os
import re
from pathlib import Path

ROOT_FILES = {"README.md", "AI_DEV_LOG.md", ".env.example", ".gitignore", "requirements.txt", "pytest.ini"}
SOURCE_DIRS = {"app", "static", "docs", "tests", "scripts"}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".uv-cache", ".cache", "data", "artifacts", "test-output"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".zip", ".rar", ".log", ".tmp"}
SOURCE_SUFFIXES = {'.py','.js','.mjs','.html','.css','.md','.json','.ps1','.txt','.ini','.yaml','.yml'}
PUBLIC_SCREENSHOTS = {'docs/screenshots/workspace-demo.png','docs/screenshots/evidence-unknown-demo.png'}
REQUIRED_FILES = ROOT_FILES | {
    'app/main.py','app/services/llm_compiler.py','app/services/llm_provider.py','app/services/compiler_models.py',
    'app/services/strategy_compiler.py','app/services/session_service.py','app/adapters/fuyao_financial.py',
    'app/adapters/fuyao_client.py','app/adapters/fuyao_validation.py','app/domain/models.py',
    'app/domain/strategy_engine.py','app/domain/volatility.py','app/store/sqlite_store.py',
    'static/index.html','static/app.js','static/styles.css','static/workspace-core.mjs',
    'docs/LLM_COMPILER.md','docs/UI_DESIGN_SPEC.md','docs/COMPETITOR_RESEARCH.md',
    'docs/FUYAO_INTEGRATION.md','docs/TEST_PLAN.md','docs/FINAL_VALIDATION.md',
    'tests/test_llm_compiler.py','scripts/eval_llm.py','scripts/final_real_validation.py','scripts/start_llm.ps1'}


def credential_scan(content):
    """Fail on actual configured credentials or token-shaped secrets; keywords alone are valid code."""
    for name in ('SILICONFLOW_API_KEY','HITHINK_FINANCE_API_KEY','ZHIPU_API_KEY','OPENAI_API_KEY','LLM_API_KEY'):
        secret=os.getenv(name,'')
        if secret and secret.encode() in content: return 'configured_credential'
    if re.search(rb'\bsk-[A-Za-z0-9_-]{20,}',content): return 'token_shaped_secret'
    return None


def release_files(root: Path):
    candidates = [root/name for name in sorted(ROOT_FILES)]
    for name in sorted(SOURCE_DIRS):
        directory = root/name
        if directory.is_dir() and not directory.is_symlink():
            candidates.extend(sorted(directory.rglob("*")))
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts) or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if path.name.startswith(".env") and relative.as_posix() != ".env.example":
            continue
        if relative.as_posix() not in ROOT_FILES | PUBLIC_SCREENSHOTS and path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            continue
        if relative.as_posix() in ROOT_FILES or relative.parts[0] in SOURCE_DIRS:
            yield path


def build_release(root: Path, output: Path):
    files = list(release_files(root))
    relative={path.relative_to(root).as_posix():path for path in files}
    missing=REQUIRED_FILES-relative.keys()
    if missing: raise ValueError('Required source files missing: '+', '.join(sorted(missing)))
    for name,path in relative.items():
        if credential_scan(path.read_bytes()): raise ValueError('Credential scan blocked: '+name)
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.building')
    with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,arcname="StrategyLens/"+path.relative_to(root).as_posix())
    rows=[]
    with zipfile.ZipFile(temporary) as archive:
        assert len(archive.namelist())==len(set(archive.namelist()))==len(files)
        assert set(archive.namelist())=={'StrategyLens/'+name for name in relative}
        for name,path in sorted(relative.items()):
            source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
            payload=archive.read('StrategyLens/'+name)
            zip_hash=hashlib.sha256(payload).hexdigest()
            if source_hash!=zip_hash or credential_scan(payload): raise ValueError('Package integrity failed: '+name)
            rows.append({'path':name,'source_sha256':source_hash,'zip_sha256':zip_hash,'match':True})
    # Windows sandbox can deny rename even for a writable test directory.
    output.write_bytes(temporary.read_bytes())
    if output.read_bytes()!=temporary.read_bytes(): raise ValueError('Final archive copy failed integrity check')
    manifest={'file_count':len(files),'all_files_match':True,'credential_scan':'passed',
              'archive_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':rows}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return len(files)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    destination = root/"artifacts"/"StrategyLens-workspace-source.zip"
    print(f"Packaged {build_release(root,destination)} source files: {destination}")
