# Repository Distiller - User Manual

## Overview

Repository Distiller creates filtered copies of code repositories optimized for LLM context preparation.

**Version:** 1.0.1 (Path Resolution Fix)  
**Updated:** 2025-12-14

## What's New in v1.0.1

**FIXED:** Major bug causing "not in the subpath" errors resolved. The distiller now correctly handles both relative paths (like `../project`) and absolute paths by resolving all paths to absolute before processing.

## Installation

### Prerequisites
- Python 3.7 or higher
- uv package manager (recommended)

### Setup with uv
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or download the project
cd repo_distiller_project

# Install dependencies
uv sync

# Verify installation
uv run python src/repo_distiller.py --version
```

## Quick Start

### Basic Usage
```bash
# From project root with uv
# Now works with BOTH relative and absolute paths!
uv run python src/repo_distiller.py ../source-project ./dest-project
uv run python src/repo_distiller.py /absolute/path/source /absolute/path/dest

# Or without uv
python src/repo_distiller.py ../source ./dest
```

### Common Options

#### Dry Run (Preview Mode)
```bash
uv run python src/repo_distiller.py ../source ./dest --dry-run
```

#### Verbose Logging
```bash
uv run python src/repo_distiller.py ../source ./dest --verbose
```

#### Custom Configuration
```bash
uv run python src/repo_distiller.py ../source ./dest --config my_config.yaml
```

## Configuration

### YAML Configuration File

The distiller uses `config.yaml` for all filtering rules.

**IMPORTANT: Regex Pattern Syntax**

Regex patterns in YAML must use **single quotes** to avoid escaping issues:

```yaml
# ✅ CORRECT: Single quotes for regex patterns
blacklist:
  patterns:
    - '_v\d{1,2}\.py$'      # Matches: *_v1.py, *_v2.py, ..., *_v99.py
    - '^step\d{1,2}'         # Matches: step1_*, step2_*, etc.
    - '^utils_'               # Matches: utils_*.py

# ❌ WRONG: Double quotes cause YAML parsing errors
blacklist:
  patterns:
    - "_v\d{1,2}\.py$"      # ERROR: unknown escape character 'd'
```

### Configuration Sections

#### 1. Whitelist Rules (Highest Priority)

Only explicitly whitelisted files/directories are included (whitelist-only mode).

```yaml
whitelist:
  files:
    - "README.md"
    - "pyproject.toml"
    - "*.md"  # Glob pattern: all markdown files
  directories:
    - "src/"
    - "output/qa/step5_gold/"
```

#### 2. Blacklist Rules

Applied to files that ARE whitelisted for fine-grained exclusion.

```yaml
blacklist:
  files:
    - ".env"
    - ".gitignore"

  extensions:
    - ".png"
    - ".jpg"
    - ".pdf"

  patterns:  # Use single quotes!
    - '_v\d{1,2}\.py$'      # Versioned files
    - '^step\d{1,2}'         # Step files
    - '^utils_'               # Utility files

  directories:
    - ".git/"
    - "node_modules/"
    - "__pycache__/"
```

#### 3. Data Sampling

For large data files, sample head + tail instead of full copy:

```yaml
data_sampling:
  enabled: true
  target_extensions:
    - ".csv"
    - ".json"
    - ".jsonl"
  include_header: true  # For CSV/TSV
  head_rows: 5
  tail_rows: 5
```

## Regex Pattern Examples

### Filter Versioned Files

```yaml
patterns:
  - '_v\d{1,2}\.py$'  # Single quotes required!
```

**Matches:**
- `adjudicate_gold_v1.py` ✗
- `adjudicate_gold_v2.py` ✗
- `adjudicate_gold.py` ✓ (no version suffix)

### Filter Step-Numbered Files

```yaml
patterns:
  - '^step\d{1,2}'  # Single quotes required!
```

**Matches:**
- `step1_generate_examples.py` ✗
- `step2_filter_dataset.py` ✗
- `process_step1.py` ✓ (doesn't start with "step")

### Filter Utility Files

```yaml
patterns:
  - '^utils_'  # Single quotes required!
```

**Matches:**
- `utils_fix_annotator.py` ✗
- `utils_helper.py` ✗
- `data_utils.py` ✓ (doesn't start with "utils_")

## Troubleshooting

### v1.0.0 Error: "not in the subpath of"

**Problem:** In v1.0.0, using relative paths like `../project` caused errors.

**Solution:** Upgrade to v1.0.1 (this version). The path resolution issue is fixed.

### "Invalid YAML: unknown escape character"

**Problem:** Regex patterns use double quotes instead of single quotes.

**Solution:** Change regex patterns to use single quotes:

```yaml
# Before (causes error):
patterns:
  - "_v\d{1,2}\.py$"

# After (correct):
patterns:
  - '_v\d{1,2}\.py$'
```

### Files not being copied as expected

**Solution:** Run with `--verbose` and `--dry-run`:

```bash
uv run python src/repo_distiller.py ../source ./dest --dry-run --verbose
```

### Permission errors

**Solution:** Ensure you have read access to source and write access to destination.

## Output Summary

After completion, you'll see a summary:

```
======================================================================
DISTILLATION SUMMARY
======================================================================
Total files scanned:  156
Files copied:         42
Files sampled:        2
Files skipped:        112
Errors:               0

Skip reasons breakdown:
  blacklist_pattern:_v\d{1,2}\.py$  : 45
  blacklist_pattern:^step\d{1,2}     : 28
  blacklist_pattern:^utils_          : 12
  blacklist_ext:.md                   : 18
  not_whitelisted                     : 9
======================================================================
```

## Exit Codes

- `0`: Success
- `1`: Error occurred
- `130`: Operation cancelled by user (Ctrl+C)

## Best Practices

1. **Always use dry run first** for new configurations
2. **Use single quotes** for regex patterns in YAML
3. **Review the summary report** to verify expected files
4. **Check log files** in `./logs/` for detailed troubleshooting

## Support

For technical details, see `docs/tech-specs.md`.
