import logging
from pathlib import Path
from typing import List, Set
import re

import pytest

import sys

# Ensure repository root is on sys.path so `src` is importable when the project
# is not installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from src.repo_distiller import DistillerConfig, RepositoryDistiller, FilterAction


@pytest.fixture()
def logger():
    log = logging.getLogger("repo_distiller_test")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    log.addHandler(logging.NullHandler())
    return log


def make_config(
    *,
    max_file_size_mb: float = 5.0,
    whitelist_files: List[str] = None,
    whitelist_directories: List[str] = None,
    blacklist_files: List[str] = None,
    blacklist_extensions: List[str] = None,
    blacklist_directories: List[str] = None,
    blacklist_patterns: List[re.Pattern] = None,
    blacklist_filename_substrings: List[str] = None,
    blacklist_datetime_stamp_yyyymmdd: bool = True,
    sampling_exts: Set[str] = None,
):
    return DistillerConfig(
        max_file_size_mb=max_file_size_mb,
        whitelist_files=whitelist_files or [],
        whitelist_directories=whitelist_directories or [],
        blacklist_files=blacklist_files or [],
        blacklist_extensions=blacklist_extensions or [],
        blacklist_patterns=blacklist_patterns or [],
        blacklist_directories=blacklist_directories or [],
        blacklist_filename_substrings=blacklist_filename_substrings or [],
        blacklist_datetime_stamp_yyyymmdd=blacklist_datetime_stamp_yyyymmdd,
        data_sampling_enabled=True,
        data_sampling_extensions=sampling_exts or {".csv", ".tsv", ".json", ".jsonl"},
        data_sampling_include_header=True,
        data_sampling_head_rows=3,
        data_sampling_tail_rows=3,
        ai_coding_env="test",
    )


def write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def write_bytes(p: Path, size: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_tier1_whitelist_file_overrides_directory_extension_and_size(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    target = repo / "node_modules" / "lib" / "README.md"
    write_bytes(target, size=2 * 1024 * 1024)  # 2MB

    cfg = make_config(
        max_file_size_mb=1.0,
        whitelist_files=["node_modules/lib/README.md"],
        whitelist_directories=["src/"],  # does not include node_modules
        blacklist_directories=["node_modules/"],
        blacklist_extensions=[".md"],
    )

    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(target, repo)

    assert action == FilterAction.COPY
    assert reason == "tier1_whitelist_file"


def test_tier2_blacklist_file_veto(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "src" / ".env"
    write_text(f, "SECRET=1")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_files=["src/.env"],
    )
    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason == "tier2_blacklist_file"


def test_tier2_datetime_stamp_veto(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "src" / "report_20251207.txt"
    write_text(f, "hello")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_datetime_stamp_yyyymmdd=True,
    )
    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason.startswith("tier2_blacklist_datetime_stamp:20251207")


def test_tier2_invalid_datetime_stamp_not_vetoed(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "src" / "report_20251340.txt"  # invalid month/day
    write_text(f, "hello")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_datetime_stamp_yyyymmdd=True,
    )
    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(f, repo)

    assert action == FilterAction.COPY
    assert reason == "tier4_copied"


def test_tier2_filename_substring_veto_case_insensitive(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "src" / "notes_bAcKuP.txt"
    write_text(f, "hello")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_filename_substrings=["BACKUP", "OLD", "ORIGINAL"],
    )
    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason.startswith("tier2_blacklist_filename_substring:")


def test_tier3_scope_gate_blocks_non_whitelisted_dirs(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "other" / "file.txt"
    write_text(f, "hello")

    cfg = make_config(
        whitelist_directories=["src/"],
    )
    d = RepositoryDistiller(cfg, logger)
    action, reason = d.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason == "tier3_not_in_whitelist_scope"


def test_sampling_csv_integration(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()
    dest = tmp_path / "dest"

    csv_file = repo / "src" / "data.csv"
    write_text(
        csv_file,
        "h1,h2\n" + "\n".join([f"{i},{i}" for i in range(20)]) + "\n",
    )

    cfg = make_config(
        whitelist_directories=["src/"],
        sampling_exts={".csv"},
        blacklist_datetime_stamp_yyyymmdd=False,  # avoid unintended skips
    )
    d = RepositoryDistiller(cfg, logger)

    ok = d.distill(repo, dest, dry_run=False)
    assert ok is True

    out = dest / "src" / "data.csv"
    assert out.exists()

    out_text = out.read_text(encoding="utf-8")
    assert "rows omitted" in out_text


def test_sampling_jsonl_integration(tmp_path: Path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()
    dest = tmp_path / "dest"

    jsonl = repo / "src" / "data.jsonl"
    lines = [f'{{"i": {i}}}' for i in range(30)]
    write_text(jsonl, "\n".join(lines) + "\n")

    cfg = make_config(
        whitelist_directories=["src/"],
        sampling_exts={".jsonl"},
        blacklist_datetime_stamp_yyyymmdd=False,
    )
    d = RepositoryDistiller(cfg, logger)

    ok = d.distill(repo, dest, dry_run=False)
    assert ok is True

    out = dest / "src" / "data.jsonl"
    assert out.exists()

    out_text = out.read_text(encoding="utf-8")
    assert "objects omitted" in out_text
