import logging
from pathlib import Path
import re

import pytest

from src.repo_distiller import DistillerConfig, RepositoryDistiller, FilterAction


@pytest.fixture()
def logger(tmp_path):
    # Quiet logger for tests
    log = logging.getLogger("repo_distiller_test")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    log.addHandler(logging.NullHandler())
    return log


def make_config(**overrides):
    cfg = dict(
        max_file_size_mb=1.0,
        whitelist_files=[],
        whitelist_directories=[],
        blacklist_files=[],
        blacklist_extensions=[],
        blacklist_patterns=[],
        blacklist_directories=[],
        data_sampling_enabled=True,
        data_sampling_extensions={".csv", ".json", ".jsonl", ".tsv"},
        data_sampling_include_header=True,
        data_sampling_head_rows=2,
        data_sampling_tail_rows=2,
        ai_coding_env="chat",
    )
    cfg.update(overrides)
    return DistillerConfig(**cfg)


def write_file(path: Path, size_bytes: int = 10, content: str = "x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if size_bytes <= 1024:
        path.write_text(content, encoding="utf-8")
    else:
        # deterministic "big" file
        with open(path, "wb") as f:
            f.write(b"a" * size_bytes)


def test_tier1_whitelist_file_overrides_blacklist_dir_ext_and_size(tmp_path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    # Big markdown file inside blacklisted directory
    target = repo / "node_modules" / "lib" / "README.md"
    write_file(target, size_bytes=2 * 1024 * 1024, content="hello")  # 2MB > 1MB

    cfg = make_config(
        whitelist_files=["node_modules/lib/README.md"],
        whitelist_directories=["src/"],  # irrelevant here
        blacklist_directories=["node_modules/"],
        blacklist_extensions=[".md"],
        max_file_size_mb=1.0,
    )
    distiller = RepositoryDistiller(cfg, logger)
    action, reason = distiller.determine_action(target, repo)

    assert action in (FilterAction.COPY, FilterAction.SAMPLE)
    assert reason.startswith("tier1_whitelist_file")


def test_tier2_blacklist_file_veto(tmp_path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    secret = repo / "src" / ".env"
    write_file(secret, content="SECRET=1")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_files=["src/.env"],
    )
    distiller = RepositoryDistiller(cfg, logger)
    action, reason = distiller.determine_action(secret, repo)

    assert action == FilterAction.SKIP
    assert reason == "tier2_blacklist_file"


def test_tier2_blacklist_pattern_veto(tmp_path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "src" / "utils_helpers.py"
    write_file(f, content="pass")

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_patterns=[re.compile(r"^utils_")],
    )
    distiller = RepositoryDistiller(cfg, logger)
    action, reason = distiller.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason.startswith("tier2_blacklist_pattern:")


def test_tier3_requires_whitelisted_directory_when_not_file_whitelisted(tmp_path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f = repo / "other" / "a.py"
    write_file(f, content="print('hi')")

    cfg = make_config(
        whitelist_directories=["src/"],
    )
    distiller = RepositoryDistiller(cfg, logger)
    action, reason = distiller.determine_action(f, repo)

    assert action == FilterAction.SKIP
    assert reason == "tier3_not_in_whitelist_scope"


def test_tier4_extension_and_size_checks_apply_in_scope(tmp_path, logger):
    repo = tmp_path / "repo"
    repo.mkdir()

    f1 = repo / "src" / "image.png"
    write_file(f1, content="not really png")

    f2 = repo / "src" / "big.txt"
    write_file(f2, size_bytes=2 * 1024 * 1024, content="big")  # 2MB

    cfg = make_config(
        whitelist_directories=["src/"],
        blacklist_extensions=[".png"],
        max_file_size_mb=1.0,
    )
    distiller = RepositoryDistiller(cfg, logger)

    a1, r1 = distiller.determine_action(f1, repo)
    assert a1 == FilterAction.SKIP
    assert r1.startswith("tier4_blacklist_ext:")

    a2, r2 = distiller.determine_action(f2, repo)
    assert a2 == FilterAction.SKIP
    assert r2.startswith("tier4_file_size>")
