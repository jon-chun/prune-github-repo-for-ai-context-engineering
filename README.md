# Repository Distiller

**Version:** 1.0.1 (Path Resolution Fix)  
**License:** MIT

## Overview

Repository Distiller is a command-line Python utility that creates intelligent, filtered copies of code repositories optimized for providing context to Large Language Models (LLMs) in AI-assisted coding workflows.

## Latest Update (v1.0.1)

**FIXED:** Path resolution issue causing "not in the subpath" errors when using relative paths like `../project-name`. All paths are now properly resolved to absolute paths before processing.

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
- ✅ **Path Resolution**: Handles both relative and absolute paths correctly

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
# Works with both relative and absolute paths
uv run python src/repo_distiller.py /path/to/source /path/to/destination
uv run python src/repo_distiller.py ../my-project ./distilled-project

# Dry run (preview only)
uv run python src/repo_distiller.py ../source ./dest --dry-run

# Verbose logging
uv run python src/repo_distiller.py ../source ./dest --verbose

# Custom configuration
uv run python src/repo_distiller.py ../source ./dest --config my_config.yaml
```

## Changelog

### v1.0.1 (2025-12-14)
- **FIXED:** Path resolution issue causing "not in the subpath" errors
- All paths now properly resolved to absolute paths using `.resolve()`
- Improved error handling for relative paths
- Enhanced logging with better path display

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
    - '_v\d{1,2}\.py$'      # Excludes: *_v1.py, *_v2.py, ..., *_v99.py
    - '^step\d{1,2}'         # Excludes: step1_*, step2_*, ...
    - '^utils_'               # Excludes: utils_*.py

# Data sampling
data_sampling:
  enabled: true
  target_extensions: [".csv", ".json", ".jsonl"]
  head_rows: 5
  tail_rows: 5
```

## Documentation

- **[User Manual](docs/user-manual.md)** - Complete usage guide, configuration reference, and troubleshooting
- **[Technical Specification](docs/tech-specs.md)** - Architecture, API documentation, and extension guide

## Requirements

- Python 3.7+
- uv package manager (recommended)
- PyYAML (`uv add pyyaml`)

## License

MIT License - See LICENSE file for details.
