# Repository Distiller

**Version:** 1.0.0  
**License:** MIT

## Overview

Repository Distiller is a command-line Python utility that creates intelligent, filtered copies of code repositories optimized for providing context to Large Language Models (LLMs) in AI-assisted coding workflows.

## Features

- ✅ **Smart Filtering**: Configurable whitelist/blacklist rules with glob pattern support
- ✅ **Whitelist-Only Mode**: Default blacklist-everything approach with explicit whitelisting
- ✅ **Data Sampling**: Automatically sample large CSV/JSON/JSONL files (head + tail)
- ✅ **Regex Patterns**: Filter versioned files, step-numbered scripts, and utility files
- ✅ **Size Control**: Skip files over configurable size threshold
- ✅ **Flexible Configuration**: YAML-based configuration with pattern matching
- ✅ **Dry Run Mode**: Preview actions before executing
- ✅ **Comprehensive Logging**: Dual-stream logging (console + file) with detailed statistics
- ✅ **AI-Optimized**: Designed specifically for LLM context preparation

## Quick Start

### Installation

```bash
# Clone or download this repository
cd repo_distiller_project

# Install with uv (recommended)
uv sync

# Or install dependencies manually
uv add pyyaml

# Verify installation
uv run python src/repo_distiller.py --version
```

### Basic Usage

```bash
# Distill a repository (from project root)
uv run python src/repo_distiller.py /path/to/source /path/to/destination

# Dry run (preview only)
uv run python src/repo_distiller.py /path/to/source /path/to/destination --dry-run

# Verbose logging
uv run python src/repo_distiller.py /path/to/source /path/to/destination --verbose

# Custom configuration
uv run python src/repo_distiller.py /path/to/source /path/to/destination --config my_config.yaml
```

## Documentation

- **[User Manual](docs/user-manual.md)** - Complete usage guide, configuration reference, and troubleshooting
- **[Technical Specification](docs/tech-specs.md)** - Architecture, API documentation, and extension guide for AI-assisted development

## Configuration Example

This project uses a **whitelist-only approach** by default. Edit `config.yaml` to customize:

```yaml
# AI coding environment: 'chat', 'ide', 'agentic', 'cli'
ai_coding_env: 'chat'

# Maximum file size in MB (applied after whitelist)
max_file_size_mb: 5

# WHITELIST: Only these are included
whitelist:
  files:
    - "README.md"
    - "pyproject.toml"
    - "config.yaml"
    # Data files (will be sampled)
    - "examples/openai/gpt-5-mini/gold-gpt5mini/*.csv"
    - "examples/openai/gpt-5-mini/gold-gpt5mini/*.json"

  directories:
    - "output/qa/step5_gold/"
    - "src/"
    - "src/qa_gold_lib/"

# BLACKLIST: Exclude from whitelisted items
blacklist:
  extensions:
    - ".png"
    - ".jpg"
    - ".pdf"
    - ".md"  # Except README.md (explicitly whitelisted)

  patterns:
    - "_v\\d{1,2}\\.py$"      # Excludes: *_v1.py, *_v2.py, ..., *_v99.py
    - "^step\\d{1,2}"         # Excludes: step1_*, step2_*, ...
    - "^utils_"               # Excludes: utils_*.py

# Data sampling
data_sampling:
  enabled: true
  target_extensions: [".csv", ".json", ".jsonl"]
  head_rows: 5
  tail_rows: 5
```

## Project Structure

```
.
├── src/
│   └── repo_distiller.py      # Main executable script
├── config.yaml                # Configuration file
├── pyproject.toml             # uv project configuration
├── README.md                  # This file
├── docs/
│   ├── user-manual.md        # User documentation
│   └── tech-specs.md         # Technical specification
├── logs/                      # Auto-generated log files
└── tests/                     # (Future) Test suite
```

## Rule Priority

Files are evaluated in this order:

1. **Whitelist** (highest priority) → Include
2. **Blacklist** (applied to whitelisted items) → Skip
3. **Data Sampling** → Sample if applicable
4. **Default** → If not whitelisted, SKIP (whitelist-only mode)

## Example: Filtering Versioned Files

Given this input directory:
```
adjudicate_gold_v1.py
adjudicate_gold_v2.py
adjudicate_gold.py
step1_generate_examples.py
step2_filter-silver-dataset.py
utils_fix_annotator_id.py
eval_models.py
```

With the provided configuration:
```
✓ eval_models.py              (in whitelisted src/ directory)
✗ adjudicate_gold_v1.py       (matches pattern: _v\d{1,2}\.py$)
✗ adjudicate_gold_v2.py       (matches pattern: _v\d{1,2}\.py$)
✓ adjudicate_gold.py          (in whitelisted directory, no version suffix)
✗ step1_generate_examples.py (matches pattern: ^step\d{1,2})
✗ step2_filter-silver-dataset.py (matches pattern: ^step\d{1,2})
✗ utils_fix_annotator_id.py  (matches pattern: ^utils_)
```

## Use Cases

### AI-Assisted Coding
Prepare repository context for chat-based coding assistants:

```bash
uv run python src/repo_distiller.py ./my-project ./my-project-distilled
# Then paste distilled files into LLM context
```

### Code Review Preparation
Create lightweight snapshots excluding build artifacts:

```bash
uv run python src/repo_distiller.py ./repo ./review-snapshot --dry-run --verbose
```

### Extract Final Versions Only
Filter out all versioned files and intermediate steps:

```yaml
# config.yaml
blacklist:
  patterns:
    - "_v\\d{1,2}\\.py$"    # Remove: *_v1.py, *_v2.py, etc.
    - "^step\\d{1,2}"         # Remove: step1_*, step2_*, etc.
    - "_backup\\d*\\."       # Remove: *_backup.py, *_backup1.csv
```

## Output Example

```
======================================================================
DISTILLATION SUMMARY
======================================================================
Total files scanned:  1523
Files copied:         342
Files sampled:        8
Files skipped:        1173
Errors:               0

Skip reasons breakdown:
  blacklist_pattern:_v\d{1,2}\.py$  : 45
  blacklist_pattern:^step\d{1,2}     : 28
  blacklist_pattern:^utils_          : 12
  blacklist_ext:.md                   : 89
  blacklist_directory                 : 892
  not_whitelisted                     : 107
======================================================================
```

## Requirements

- Python 3.7+
- uv package manager (recommended)
- PyYAML (`uv add pyyaml`)

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests (when implemented)
uv run pytest

# Format code
uv run black src/

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

### Architecture

This project follows spec-driven development practices optimized for AI-assisted coding. See `docs/tech-specs.md` for:

- Complete API documentation with type signatures
- Architecture diagrams
- Extension points
- Debugging guide

## Contributing

Contributions are welcome! Please:

1. Review `docs/tech-specs.md` for architecture details
2. Follow existing code style (black, ruff)
3. Add type hints for all functions
4. Add tests for new features
5. Update documentation

## License

MIT License - See LICENSE file for details.

## Support

- Documentation: See `docs/` directory
- Examples: See configuration examples in `config.yaml`
- Technical details: See `docs/tech-specs.md`

## Changelog

### v1.0.0 (2025-12-14)
- Initial release
- Core filtering engine with whitelist/blacklist support
- Whitelist-only mode for secure filtering
- Data sampling for CSV/JSON/JSONL files
- Regex pattern matching for versioned files
- Comprehensive logging and statistics
- Dry run mode
- YAML configuration
- uv package manager support
- Moved executable code to src/ directory
