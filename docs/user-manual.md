# Repository Distiller - User Manual

## Overview

Repository Distiller is a command-line utility that creates a filtered, lightweight copy of a code repository optimized for providing context to Large Language Models (LLMs) in AI-assisted coding workflows.

**New in v1.0.0:** Whitelist-only approach, uv package manager support, and advanced regex pattern matching.

## Installation

### Prerequisites
- Python 3.7 or higher
- uv package manager (recommended)

### Setup with uv (Recommended)
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

### Setup without uv
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install pyyaml

# Verify installation
python src/repo_distiller.py --version
```

## Quick Start

### Basic Usage
```bash
# From project root with uv
uv run python src/repo_distiller.py <source_directory> <destination_directory>

# Or without uv
python src/repo_distiller.py <source_directory> <destination_directory>
```

**Example:**
```bash
uv run python src/repo_distiller.py ./my-project ./my-project-distilled
```

### Common Options

#### Dry Run (Preview Mode)
Preview what actions would be taken without actually copying files:
```bash
uv run python src/repo_distiller.py ./source ./dest --dry-run
```

#### Verbose Logging
Enable detailed DEBUG-level logging:
```bash
uv run python src/repo_distiller.py ./source ./dest --verbose
```

#### Custom Configuration
Use a custom configuration file:
```bash
uv run python src/repo_distiller.py ./source ./dest --config my_config.yaml
```

#### Help
```bash
uv run python src/repo_distiller.py --help
```

## Configuration

### Configuration File Structure

The distiller is controlled by a YAML configuration file (default: `./config.yaml`).

### Key Configuration Sections

#### 1. AI Coding Environment
```yaml
ai_coding_env: 'chat'  # Options: 'chat', 'ide', 'agentic', 'cli'
```

#### 2. Maximum File Size
```yaml
max_file_size_mb: 5
```

Files larger than this size (in MB) will be skipped, **unless** they are explicitly whitelisted.

#### 3. Whitelist Rules (Highest Priority)

**NEW:** Whitelist-only mode - only explicitly whitelisted items are included.

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

**Supports glob patterns**:
- `*` - matches any characters within a filename
- `**` - matches any directories recursively

#### 4. Blacklist Rules

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
    - ".md"  # Note: README.md is explicitly whitelisted

  patterns:  # Python regex patterns
    - "_v\\d{1,2}\\.py$"      # Matches: file_v1.py through file_v99.py
    - "^step\\d{1,2}"         # Matches: step1_*, step2_*, etc.
    - "^utils_"               # Matches: utils_*.py
    - "\\.bak$"                # Matches: file.bak

  directories:
    - ".git/"
    - "node_modules/"
    - "__pycache__/"
```

#### 5. Data Sampling

For large structured data files, the distiller can create samples instead of copying the entire file.

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

**Sampled output format:**
- **CSV/TSV**: Header + first 5 rows + separator comment + last 5 rows
- **JSON arrays**: Restructured object with `head` and `tail` keys
- **JSONL**: First 5 objects + separator + last 5 objects

## Rule Priority

The distiller applies rules in this exact order for each file:

1. **Whitelist Check** (Highest Priority)
   - If file/directory is whitelisted → Proceed to step 2
   - If NOT whitelisted → **SKIP** (whitelist-only mode)

2. **Blacklist Check** (Applied to whitelisted items)
   - Check: specific files, directories, extensions, regex patterns, file size
   - If any blacklist rule matches → **SKIP**

3. **Data Sampling Check**
   - If file extension matches `data_sampling.target_extensions`
   - AND data sampling is enabled → **SAMPLE** instead of full copy

4. **Default Action**
   - If whitelisted and not blacklisted → **COPY** verbatim

## Regex Pattern Examples

### Filter Versioned Files

Exclude all files with version suffixes:

```yaml
patterns:
  - "_v\\d{1,2}\\.py$"  # Matches: *_v1.py, *_v2.py, ..., *_v99.py
```

**Example matches:**
- `adjudicate_gold_v1.py` ✗
- `adjudicate_gold_v2.py` ✗
- `adjudicate_gold_v15.py` ✗
- `adjudicate_gold.py` ✓ (no version suffix)

### Filter Step-Numbered Files

Exclude workflow step files:

```yaml
patterns:
  - "^step\\d{1,2}"  # Matches: step1_*, step2_*, ..., step99_*
```

**Example matches:**
- `step1_generate_examples.py` ✗
- `step2_filter_dataset.py` ✗
- `step10_final_process.py` ✗
- `process_step1.py` ✓ (doesn't start with "step")

### Filter Utility Files

Exclude utility scripts:

```yaml
patterns:
  - "^utils_"  # Matches: utils_*.py
```

**Example matches:**
- `utils_fix_annotator.py` ✗
- `utils_helper.py` ✗
- `data_utils.py` ✓ (doesn't start with "utils_")

## Logging

The distiller maintains two log outputs:

1. **Console output**: Concise, human-readable
2. **File log**: `./logs/log_YYYYMMDD_HHMMSS.txt` - detailed with timestamps

### Log Levels
- **INFO** (default): Summary information and major actions
- **DEBUG** (with `--verbose`): Detailed decision-making for every file

## Output Summary

After completion, the distiller prints a summary report:

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

1. **Always use dry run first** for new configurations:
   ```bash
   uv run python src/repo_distiller.py ./source ./dest --dry-run --verbose
   ```

2. **Start with explicit whitelisting** for maximum control

3. **Use regex patterns** to filter versioned files and intermediate steps

4. **Review the summary report** to ensure expected files are included

5. **Check log files** in `./logs/` for detailed troubleshooting

## Troubleshooting

### "Configuration file not found"
**Solution**: Ensure `config.yaml` exists in the current directory, or specify path with `--config`

### "Source directory does not exist"
**Solution**: Verify the source path is correct and accessible

### Files not being copied as expected
**Solution**: Run with `--verbose` and `--dry-run` to see decision-making:
```bash
uv run python src/repo_distiller.py ./source ./dest --dry-run --verbose | grep "filename"
```

### Regex pattern not matching
**Solution**: Test your regex in Python:
```python
import re
pattern = re.compile(r"_v\d{1,2}\.py$")
print(pattern.search("adjudicate_gold_v1.py"))  # Should match
```

### Permission errors
**Solution**: Ensure you have read access to source and write access to destination

## Advanced Usage

### Combining with Context Preparation Tools

The distiller is designed to work as part of an LLM context preparation pipeline:

```bash
# 1. Distill repository
uv run python src/repo_distiller.py ./my-repo ./distilled

# 2. Generate context document for LLM
find ./distilled -name "*.py" -exec cat {} \; > context_for_llm.txt
```

### Custom Sampling Logic

For specialized data formats, modify the `_sample_csv_file()` or `_sample_json_file()` methods in `src/repo_distiller.py`.

## Configuration Examples

### Example 1: Python Project (Final Versions Only)
```yaml
ai_coding_env: 'chat'
max_file_size_mb: 5

whitelist:
  files:
    - "README.md"
    - "pyproject.toml"
    - "*.md"
  directories:
    - "src/"
    - "tests/"

blacklist:
  extensions:
    - ".pyc"
    - ".pyo"
  patterns:
    - "_v\\d{1,2}\\.py$"      # Remove versioned files
    - "^step\\d{1,2}"         # Remove step files
    - "^utils_"               # Remove utility scripts
  directories:
    - "__pycache__/"
    - "venv/"
    - ".pytest_cache/"

data_sampling:
  enabled: true
  target_extensions: [".csv", ".json"]
  head_rows: 10
  tail_rows: 10
```

### Example 2: Extract Gold Dataset Only
```yaml
ai_coding_env: 'chat'
max_file_size_mb: 10

whitelist:
  files:
    - "README.md"
    - "config.yaml"
  directories:
    - "output/qa/step5_gold/"
    - "src/"

blacklist:
  extensions:
    - ".png"
    - ".jpg"
    - ".pdf"
  patterns:
    - "_v\\d{1,2}\\."
    - "^step\\d{1,2}"
  directories:
    - "__pycache__/"

data_sampling:
  enabled: true
  target_extensions: [".csv", ".json", ".jsonl"]
  head_rows: 5
  tail_rows: 5
```

## Glossary

- **Distillation**: The process of filtering a repository to create a lightweight copy
- **Whitelist-Only Mode**: Only explicitly whitelisted files/directories are included (default)
- **Whitelist**: Rules that force inclusion of files/directories (highest priority)
- **Blacklist**: Rules that exclude files/directories from whitelisted items
- **Glob Pattern**: A pattern with wildcards (* and **) for matching multiple files
- **Regex Pattern**: Python-compatible regular expression for advanced filename matching
- **Data Sampling**: Creating a partial copy of large data files (head + tail)
- **Dry Run**: Preview mode that shows actions without executing them

## Support

For technical details, see `docs/tech-specs.md`.

For issues or contributions, refer to the project repository.

## Version History

### v1.0.0 (2025-12-14)
- Initial release
- Core filtering engine
- Whitelist-only mode
- Regex pattern matching for versioned files
- Data sampling for CSV/JSON/JSONL
- Comprehensive logging
- Dry run mode
- uv package manager support
- Moved executable code to src/ directory
