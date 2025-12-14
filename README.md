# Repository Distiller

**Version:** 1.0.0  
**License:** MIT

## Overview

Repository Distiller is a command-line Python utility that creates intelligent, filtered copies of code repositories optimized for providing context to Large Language Models (LLMs) in AI-assisted coding workflows.

## Features

- ✅ **Smart Filtering**: Configurable whitelist/blacklist rules with glob pattern support
- ✅ **Data Sampling**: Automatically sample large CSV/JSON/JSONL files (head + tail)
- ✅ **Size Control**: Skip files over configurable size threshold
- ✅ **Flexible Configuration**: YAML-based configuration with regex pattern support
- ✅ **Dry Run Mode**: Preview actions before executing
- ✅ **Comprehensive Logging**: Dual-stream logging (console + file) with detailed statistics
- ✅ **AI-Optimized**: Designed specifically for LLM context preparation

## Quick Start

### Installation

```bash
# Clone or download this repository
cd repo_distiller_project

# Install dependencies
pip install pyyaml

# Make script executable (Unix/Linux/Mac)
chmod +x repo_distiller.py
```

### Basic Usage

```bash
# Distill a repository
python repo_distiller.py /path/to/source /path/to/destination

# Dry run (preview only)
python repo_distiller.py /path/to/source /path/to/destination --dry-run

# Verbose logging
python repo_distiller.py /path/to/source /path/to/destination --verbose

# Custom configuration
python repo_distiller.py /path/to/source /path/to/destination --config my_config.yaml
```

## Documentation

- **[User Manual](docs/user-manual.md)** - Complete usage guide, configuration reference, and troubleshooting
- **[Technical Specification](docs/tech-specs.md)** - Architecture, API documentation, and extension guide for AI-assisted development

## Configuration

Edit `config.yaml` to customize filtering behavior:

```yaml
# AI coding environment: 'chat', 'ide', 'agentic', 'cli'
ai_coding_env: 'chat'

# Maximum file size in MB
max_file_size_mb: 5

# Whitelist (always include)
whitelist:
  files:
    - "README.md"
    - "*.md"
  directories:
    - "src/"
    - "tests/"

# Blacklist (exclude unless whitelisted)
blacklist:
  files:
    - ".env"
    - ".gitignore"
  extensions:
    - ".log"
    - ".pyc"
    - ".png"
  patterns:
    - "_v\\d+\\."  # Matches: file_v1.py
  directories:
    - ".git/"
    - "node_modules/"

# Data sampling for large files
data_sampling:
  enabled: true
  target_extensions: [".csv", ".json", ".jsonl"]
  head_rows: 5
  tail_rows: 5
```

## Rule Priority

Files are evaluated in this order:

1. **Whitelist** (highest priority) → Include
2. **Blacklist** → Skip
3. **Data Sampling** → Sample if applicable
4. **Default** → Copy verbatim

## Use Cases

### AI-Assisted Coding
Prepare repository context for chat-based coding assistants (Claude, ChatGPT, etc.):

```bash
python repo_distiller.py ./my-project ./my-project-distilled
# Then paste distilled files into LLM context
```

### Code Review Preparation
Create lightweight snapshots excluding build artifacts and dependencies:

```bash
python repo_distiller.py ./repo ./review-snapshot --dry-run
```

### Documentation Generation
Extract only documentation and source code:

```yaml
# config.yaml
whitelist:
  directories:
    - "src/"
    - "docs/"
  files:
    - "*.md"
    - "*.rst"
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
  blacklist_directory               : 892
  blacklist_ext:.pyc                : 156
  file_size>5MB                     : 89
  blacklist_file                    : 36
======================================================================
```

## Requirements

- Python 3.7+
- PyYAML (`pip install pyyaml`)

## Project Structure

```
.
├── repo_distiller.py          # Main executable
├── config.yaml                # Configuration file
├── README.md                  # This file
├── docs/
│   ├── user-manual.md        # User documentation
│   └── tech-specs.md         # Technical specification
├── logs/                      # Auto-generated log files
└── tests/                     # (Future) Test suite
```

## Development

This project follows spec-driven development practices optimized for AI-assisted coding. See `docs/tech-specs.md` for:

- Complete API documentation with type signatures
- Architecture diagrams
- Extension points
- Debugging guide

## Contributing

Contributions are welcome! Please:

1. Review `docs/tech-specs.md` for architecture details
2. Follow existing code style and type hints
3. Add tests for new features
4. Update documentation

## License

MIT License - See LICENSE file for details.

## Support

- Issues: File via your project repository
- Documentation: See `docs/` directory
- Examples: See configuration examples in `config.yaml`

## Changelog

### v1.0.0 (2025-12-14)
- Initial release
- Core filtering engine with whitelist/blacklist support
- Data sampling for CSV/JSON/JSONL files
- Comprehensive logging and statistics
- Dry run mode
- YAML configuration
