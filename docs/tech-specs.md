# Repository Distiller — Technical Specification

## 1. Purpose

Repository Distiller is a Python CLI that produces a **filtered, context-optimized copy** of a source repository for LLM/AI-assisted development workflows. It applies an explicit **Priority Cascade** to decide whether each file is **copied verbatim**, **sampled**, or **skipped**.

Primary goals:

- Minimize prompt tokens by excluding noise and sampling large data files.
- Preserve developer intent through explicit, deterministic precedence rules.
- Provide auditable operation via structured skip reasons and detailed logs.

## 2. Architecture

### 2.1 Module Layout

- `src/repo_distiller.py` — All core logic and CLI entrypoint.
- `config.yaml` — Default configuration.
- `docs/` — User manual and this tech spec.
- `tests/` — Pytest unit/integration tests.

### 2.2 Key Types

#### `FilterAction` (Enum)

- `COPY` — copy file verbatim to destination
- `SAMPLE` — copy a reduced representation (head/tail) to destination
- `SKIP` — do not copy

#### `FilterStats` (Dataclass)

Tracks:

- scanned, copied, sampled, skipped, errors
- `skipped_reasons: Dict[str, int]` aggregated by reason strings

#### `DistillerConfig` (Dataclass)

Represents parsed configuration and precompiled regex patterns.

Key config groups:

- Whitelist: `whitelist_files`, `whitelist_directories`
- Blacklist: `blacklist_files`, `blacklist_patterns`, `blacklist_extensions`, `blacklist_directories`
- Filename vetoes: `blacklist_filename_substrings`, `blacklist_datetime_stamp_yyyymmdd`
- Sampling: enablement and per-format parameters

## 3. Priority Cascade Decision Model

The decision engine is implemented in `RepositoryDistiller.determine_action()`.

### Tier 1 — Golden Ticket: `whitelist.files`

If the repository-relative file path matches `whitelist.files` (glob), the file is **force-included**:

- The file is copied or sampled (if eligible).
- **Bypasses**: `blacklist.directories`, `blacklist.extensions`, and `max_file_size_mb`.

Rationale: Explicit file includes should be honored even if they live in generally excluded areas.

### Tier 2 — Explicit Veto: filename-level blacklists

Tier 2 checks are evaluated against the **filename** (not the full path), unless explicitly stated.

A file is skipped immediately if any Tier 2 veto triggers:

1. `blacklist.files` (glob match against repo-relative path)
2. Datetime stamp in filename (`YYYYMMDD`), when enabled (`blacklist.datetime_stamp_yyyymmdd`)
3. Case-insensitive “contains” match against `blacklist.filename_substrings`
4. `blacklist.patterns` (regex evaluated against filename)

Rationale: Tier 2 rules provide a security/noise “kill switch” for sensitive or irrelevant files.

### Tier 3 — Scope Gate: `whitelist.directories`

Whitelist-only safety is enforced via a directory scope check:

- If the file is not under a whitelisted directory, the result is `SKIP` with reason `tier3_not_in_whitelist_scope`.

Tier 1 can still include a file outside these directories.

### Tier 4 — Sanity Exclusions: general skip rules

Tier 4 rules apply only after Tier 3 passes:

1. `blacklist.directories` (repo-relative path prefix checks)
2. `blacklist.extensions`
3. `max_file_size_mb` (file size cap in MB)

If any rule triggers, the file is skipped with a Tier 4 reason.

### Final decision — Sampling vs Copy

If the file is eligible for sampling (`data_sampling.enabled` and extension is in `data_sampling.target_extensions`):

- return `SAMPLE`
- otherwise return `COPY`

## 4. Sampling Semantics

### CSV / TSV

- Streams the file row-by-row.
- Output includes:
  - optional header row
  - first `head_rows` data rows
  - a single separator line indicating omitted row count
  - last `tail_rows` data rows
- If the file is small enough (≤ head_rows + tail_rows [+ header]), it is copied intact.

### JSONL

- Streams line-by-line.
- Preserves first N non-empty lines and last M non-empty lines.
- Inserts an omission marker.

### JSON

- If the top-level JSON value is an array: writes a sampled wrapper:
  - metadata fields (`_sampled`, `_total_items`, `_omitted_items`)
  - `head` and `tail` arrays
- If it is an object or primitive: copied intact.

## 5. Path Handling & Normalization

- All working paths are resolved to absolute paths prior to relative computations to avoid `Path.relative_to()` failures across mixed absolute/relative inputs.
- All matching is performed against repository-relative **POSIX** strings for stable cross-platform behavior.

## 6. Logging

Two handlers are configured:

- Console: concise, INFO by default
- File: detailed, DEBUG

Each skip includes an attributable reason string, and the run prints an aggregated breakdown.

## 7. Performance Considerations

- Sampling avoids loading JSONL and delimited files entirely into memory.
- Directory walking uses `Path.rglob('*')`; filtering happens per-file.

## 8. Known Tradeoffs

- Tier 2 substring vetoes are intentionally broad “contains” matches; short tokens (e.g., `BU`) can over-match.
- `whitelist.directories` is a scope gate, not a copy-list: Tier 4 may still exclude files within scope.

