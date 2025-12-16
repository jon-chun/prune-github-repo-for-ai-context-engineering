# Repository Distiller

A deterministic CLI utility that creates **filtered, context-optimized copies** of source repositories for LLM/AI-assisted development. It applies a **Priority Cascade** (explicit includes, explicit vetoes, scope gating, and sanity exclusions) and supports **head/tail sampling** for structured data files.

## Why this exists

Large repositories contain noise (build artifacts, caches, datasets, vendor trees) that waste tokens and degrade reasoning quality. Repository Distiller helps you:

- Generate a minimal snapshot for LLM prompt context
- Create small, shareable repro cases
- Exclude sensitive artifacts reliably
- Sample large datasets without copying them wholesale

## Key features

- **Priority Cascade filtering**
  - Tier 1: explicit file allowlist (“Golden Ticket”)
  - Tier 2: explicit vetoes (files, regex patterns, date-stamps, substrings)
  - Tier 3: whitelist-only directory scope gate
  - Tier 4: general exclusions (directories, extensions, size)
- **Data sampling** for `.csv`, `.tsv`, `.json`, `.jsonl`
- **Cross-platform stable matching** using repo-relative POSIX paths
- **Auditable results** with skip reason breakdowns and log files
- **Dry run mode** for safe iteration

## Project status

- Current version: **v1.1.1**
- Python: **3.7+**
- Dependencies: `PyYAML` (plus standard library)

## Repository layout

```text
.
├── config.yaml
├── docs/
├── src/
├── tests/
└── ...
```

## Setup

### Option A: `uv` (recommended)

```bash
uv sync
```

### Option B: pip

```bash
pip install -r requirements.txt
```

## Running

Basic usage:

```bash
uv run python src/repo_distiller.py <SOURCE_DIR> <DEST_DIR>
```

Common options:

```bash
# Preview decisions without writing files
uv run python src/repo_distiller.py ./my-repo ./distilled --dry-run

# Verbose logging (DEBUG) + custom config
uv run python src/repo_distiller.py ./my-repo ./distilled --verbose --config ./config.yaml

# Choose a custom log directory
uv run python src/repo_distiller.py ./my-repo ./distilled --log-dir ./logs
```

## Configuration

The default `config.yaml` is extensively commented. Conceptually:

### Tier 1 — `whitelist.files` (force-include)

- Matches repo-relative paths (glob).
- Bypasses:
  - `blacklist.directories`
  - `blacklist.extensions`
  - `max_file_size_mb`

Use Tier 1 for “I absolutely need this file” includes.

### Tier 2 — explicit vetoes (force-exclude)

Evaluated early to block sensitive/noisy files:

- `blacklist.files` (glob, repo-relative path)
- `blacklist.datetime_stamp_yyyymmdd` (filename contains a valid `YYYYMMDD`)
- `blacklist.filename_substrings` (case-insensitive, filename contains token)
- `blacklist.patterns` (regex against filename)

### Tier 3 — `whitelist.directories` (scope gate)

In whitelist-only mode, a file must live under at least one scope directory unless it is Tier 1-included.

### Tier 4 — sanity exclusions (general noise reduction)

Applied only after Tier 3 passes:

- `blacklist.directories`
- `blacklist.extensions`
- `max_file_size_mb`

### Data sampling

Enable and tune:

```yaml
data_sampling:
  enabled: true
  target_extensions: [".csv", ".tsv", ".json", ".jsonl"]
  include_header: true
  head_rows: 5
  tail_rows: 5
```

## Debugging & observability

- Console output is concise.
- A log file is always written (location printed at start).
- Use `--verbose` for per-file evaluation details.

Recommended workflow:

1. Start with `--dry-run --verbose`
2. Adjust config until the skip reason breakdown looks correct
3. Run without `--dry-run` to generate the distilled output

## Testing

Install dev deps (if using `uv`, add `pytest`), then run:

```bash
pytest -q
```

Tests cover:
- Tier ordering and precedence
- Filename date-stamp and substring vetoes
- Sampling behavior for CSV/JSON/JSONL
- Integration: end-to-end distillation into a destination directory

## Documentation

- `docs/user-manual.md` — usage and troubleshooting
- `docs/tech-specs.md` — architecture and decision model

## License

MIT (see `LICENSE`).

