import json
import zipfile

from scripts.package_release import build_release, REQUIRED_FILES
import pytest
from scripts import smoke_fuyao


def test_source_package_excludes_local_runtime_and_credentials(tmp_path):
    root = tmp_path/"project"
    root.mkdir()
    for name in REQUIRED_FILES:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture',encoding='utf-8')
    for name in ("README.md",".env.example",".env",".env.local","data/live.sqlite3", ".venv/keep.txt",
                 ".uv-cache/keep.txt", ".pytest_cache/keep.txt", "app/main.py", "app/__pycache__/main.pyc",
                 "tests/fixtures/official-schema-synthetic.json", "test-output/result.json", "old.rar"):
        path = root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("fixture",encoding="utf-8")
    out = tmp_path/"release.zip"
    expected={'StrategyLens/'+name for name in REQUIRED_FILES}|{'StrategyLens/tests/fixtures/official-schema-synthetic.json'}
    assert build_release(root,out) == len(expected)
    with zipfile.ZipFile(out) as archive:
        assert set(archive.namelist()) == expected
    manifest=json.loads(out.with_suffix('.manifest.json').read_text())
    assert manifest['all_files_match'] and all(row['source_sha256']==row['zip_sha256'] for row in manifest['files'])
    assert (root/".venv/keep.txt").exists() and (root/"data/live.sqlite3").exists()


def test_package_rejects_missing_runtime_compiler(tmp_path):
    with pytest.raises(ValueError,match='llm_compiler.py'): build_release(tmp_path,tmp_path/'release.zip')


def test_package_rejects_real_environment_secret(monkeypatch,tmp_path):
    monkeypatch.setenv('SILICONFLOW_API_KEY','fixture-sensitive-sentinel')
    for name in REQUIRED_FILES:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    (tmp_path/'README.md').write_text('fixture-sensitive-sentinel')
    with pytest.raises(ValueError,match='Credential scan blocked'):build_release(tmp_path,tmp_path/'release.zip')


def test_smoke_without_key_records_not_verified_without_constructing_provider(monkeypatch,tmp_path,capsys):
    monkeypatch.delenv("HITHINK_FINANCE_API_KEY",raising=False)
    def forbidden():
        raise AssertionError("No key: must not initialize live provider or make financial requests")
    monkeypatch.setattr(smoke_fuyao,"FuyaoFinancialDataProvider",forbidden)
    report_path = tmp_path/"not-verified.json"
    assert smoke_fuyao.main(["--full","--output",str(report_path)]) == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "not_verified"
    assert report["successful_capabilities"] == [] and report["full_universe_measured"] is False
    assert "not_verified" in capsys.readouterr().out
