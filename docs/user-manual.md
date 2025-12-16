# Repository Distiller — User Manual

## 1. What this tool does

Repository Distiller creates a **new directory** containing a curated subset of a source repository. The output is intended for:

- LLM prompt context
- code review snapshots
- redacted / minimized repro cases
- generating “clean-room” working sets

The tool is deterministic: given the same config and repo state, it will produce the same filtered output.

## 2. Installation

### 2.1 Requirements

- Python 3.7+
- `PyYAML`
- Recommended: `uv` (fast Python package manager)

### 2.2 Install dependencies

Using `uv`:

```bash
uv sync
```

Or using pip:

```bash
pip install -r requirements.txt
```

## 3. Running the distiller

From the repository root:

```bash
uv run python src/repo_distiller.py <SOURCE_DIR> <DEST_DIR>
```

Common options:

- `--dry-run` — show decisions without writing files
- `--verbose` — debug logging
- `--config PATH` — use a custom YAML config
- `--log-dir PATH` — put logs in a custom folder

Examples:

```bash
# Preview actions
uv run python src/repo_distiller.py ./my-repo ./distilled --dry-run

# Use a custom config and verbose logging
uv run python src/repo_distiller.py ./my-repo ./distilled -c ./config.yaml --verbose
```

## 4. How filtering works (practical rules)

The filter engine uses a Priority Cascade:

1. **Tier 1 (whitelist.files)**: force-include a specific file, even if it lives under a generally excluded directory, has a blacklisted extension, or exceeds `max_file_size_mb`.
2. **Tier 2 (explicit vetoes)**: force-exclude files matching:
   - `blacklist.files`
   - filename contains a valid `YYYYMMDD` date stamp (when enabled)
   - filename contains any configured `filename_substrings` (case-insensitive)
   - `blacklist.patterns` regex matches (filename only)
3. **Tier 3 (whitelist.directories)**: whitelist-only safety gate — if the file isn’t inside an allowed directory, it’s skipped.
4. **Tier 4 (general exclusions)**: applied only after Tier 3 passes:
   - directory blacklist
   - extension blacklist
   - size cap

Finally, eligible data files are **sampled**, otherwise **copied**.

## 5. Configuration reference

The default configuration file is `config.yaml`.

### 5.1 Whitelist

```yaml
whitelist:
  files:
    - "README.md"
    - "src/repo_distiller.py"
  directories:
    - "src/"
    - "docs/"
```

### 5.2 Blacklist

```yaml
blacklist:
  files:
    - ".env"
  filename_substrings:
    - "BACKUP"
  datetime_stamp_yyyymmdd: true
  patterns:
    - '_v\d{1,2}\.py$'
  extensions:
    - ".png"
  directories:
    - ".git/"
```

Guidance:

- Prefer using Tier 2 `blacklist.files` / `blacklist.patterns` for “must not include” content.
- Use Tier 4 `blacklist.directories` / `blacklist.extensions` for general noise reduction.
- Treat `filename_substrings` carefully; short tokens can over-match.

### 5.3 Data sampling

```yaml
data_sampling:
  enabled: true
  target_extensions: [".csv", ".tsv", ".json", ".jsonl"]
  include_header: true
  head_rows: 5
  tail_rows: 5
```

## 6. Understanding logs & skip reasons

Each skipped file increments a reason counter. Typical reasons:

- `tier1_whitelist_file` / `tier1_whitelist_file_sampled`
- `tier2_blacklist_file`
- `tier2_blacklist_datetime_stamp:20251207`
- `tier2_blacklist_filename_substring:BACKUP`
- `tier2_blacklist_pattern:<pattern>`
- `tier3_not_in_whitelist_scope`
- `tier4_blacklist_directory`
- `tier4_blacklist_ext:.png`
- `tier4_file_size>5MB`

Use `--verbose` to see per-file decisions in the log file.

## 7. Troubleshooting

### 7.1 “Why was my file skipped?”

1. Run with `--dry-run --verbose`
2. Check the log file path printed at startup
3. Search for the file path and read its skip reason

### 7.2 YAML regex parsing errors

Use **single quotes** around regex strings:

```yaml
patterns:
  - '_v\d{1,2}\.py$'
```

### 7.3 Destination directory overwrite prompt

If the destination exists, the tool asks before deleting it. In CI environments, prefer:
- pass a fresh destination directory, or
- delete it before running

## 8. Security notes

- Treat configs as security controls. Tier 2 vetoes are intended to block secrets and private artifacts.
- Always validate the distilled output before sharing externally.

