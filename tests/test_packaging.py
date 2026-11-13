"""AC-9: zero runtime dependencies, metadata, build artifacts, repo hygiene."""

import ast
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import speakerjoin

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "speakerjoin"


def test_pyproject_declares_no_runtime_dependencies():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies = \[\]$", text, re.MULTILINE)
    assert 'requires-python = ">=3.10"' in text
    assert 'license = "MIT"' in text
    assert 'speakerjoin = "speakerjoin.cli:main"' in text


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match
    assert match.group(1) == speakerjoin.__version__


def test_sources_import_only_the_standard_library():
    stdlib = set(sys.stdlib_module_names)
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                assert name in stdlib, f"{path.name} imports non-stdlib module {name}"


def test_public_api_is_exported():
    for name in speakerjoin.__all__:
        assert hasattr(speakerjoin, name), name
    assert (SRC / "py.typed").exists()


def test_ci_matrix_covers_the_minimum_python():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for version in ("3.10", "3.12", "3.14"):
        assert version in ci
    assert "ruff check" in ci


def test_demo_output_folder_is_ignored():
    assert "speakerjoin-demo/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "speakerjoin-demo" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_no_local_paths_in_tracked_text():
    needles = ["/" + "Users/", "/" + "Volumes/", "/private/" + "tmp"]
    skip = {".venv", ".git", "uv.lock", ".pytest_cache", ".ruff_cache", "dist", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix not in {
            ".py",
            ".md",
            ".toml",
            ".yml",
            ".json",
            ".rttm",
            ".srt",
            ".vtt",
            ".txt",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, f"{path.relative_to(ROOT)} contains {needle!r}"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_uv_build_produces_wheel_and_sdist(tmp_path):
    proc = subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    wheels = list(tmp_path.glob("*.whl"))
    sdists = list(tmp_path.glob("*.tar.gz"))
    assert len(wheels) == 1 and len(sdists) == 1
    names = zipfile.ZipFile(wheels[0]).namelist()
    assert "speakerjoin/py.typed" in names
    assert "speakerjoin/samples/meeting.rttm" in names
    assert "speakerjoin/samples/meeting.whisper.json" in names
    meta = next(n for n in names if n.endswith("METADATA"))
    metadata = zipfile.ZipFile(wheels[0]).read(meta).decode()
    assert "Requires-Dist" not in metadata  # zero runtime dependencies
    assert "License-Expression: MIT" in metadata


def test_example_script_runs(capsys):
    import runpy

    runpy.run_path(str(ROOT / "examples" / "merge_sample.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "words: 39, unassigned: 3" in out
    assert "differ on 8 words" in out
    assert "[Alice] Welcome everyone" in out
    assert "unassigned_ratio=0.0769 > 0.05" in out
