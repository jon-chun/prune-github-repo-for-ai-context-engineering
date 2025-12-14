# Repository Distiller - User Manual

## Overview

Repository Distiller is a command-line utility that creates a filtered, lightweight copy of a code repository optimized for providing context to Large Language Models (LLMs) in AI-assisted coding workflows.

## Installation

### Prerequisites
- Python 3.7 or higher
- PyYAML library

### Setup
```bash
# Install dependencies
pip install pyyaml

# Make the script executable (Unix/Linux/Mac)
chmod +x repo_distiller.py
```

## Quick Start

### Basic Usage
```bash
python repo_distiller.py <source_directory> <destination_directory>
```

**Example:**
```bash
python repo_distiller.py ./my-project ./my-project-distilled
```

### Common Options

#### Dry Run (Preview Mode)
Preview what actions would be taken without actually copying files:
```bash
python repo_distiller.py ./source ./dest --dry-run
```

#### Verbose Logging
Enable detailed DEBUG-level logging:
```bash
python repo_distiller.py ./source ./dest --verbose
```

#### Custom Configuration
Use a custom configuration file:
```bash
python repo_distiller.py ./source ./dest --config my_config.yaml
```

#### Help
```bash
python repo_distiller.py --help
```

## Configuration

### Configuration File Structure

The distiller is controlled by a YAML configuration file (default: `./config.yaml`).

### Key Configuration Sections

#### 1. AI Coding Environment
```yaml
ai_coding_env: 'chat'  # Options: 'chat', 'ide', 'agentic', 'cli'
```

This setting indicates the target AI coding environment and can be used to optimize output formatting.

#### 2. Maximum File Size
```yaml
max_file_size_mb: 5
```

Files larger than this size (in MB) will be skipped, **unless** they are explicitly whitelisted.

#### 3. Whitelist Rules (Highest Priority)

Whitelisted files/directories are **always included**, overriding all blacklist rules and size limits.

```yaml
whitelist:
  files:
    - "README.md"
    - "*.md"  # Glob pattern: all markdown files
  directories:
    - "src/"
    - "tests/"
```

**Supports glob patterns**:
- `*` - matches any characters within a filename
- `**` - matches any directories recursively (use with caution)

#### 4. Blacklist Rules

Applied to files that are NOT whitelisted.

```yaml
blacklist:
  files:
    - ".env"
    - ".gitignore"

  extensions:
    - ".log"
    - ".pyc"
    - ".png"

  patterns:  # Python regex patterns
    - "_v\\d+\\."  # Matches: file_v1.py, file_v2.txt
    - "\\.bak$"    # Matches: file.bak

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
   - If file/directory is whitelisted → **Include** (proceed to step 3)

2. **Blacklist Check** (If not whitelisted)
   - Check: specific files, directories, extensions, regex patterns, file size
   - If any blacklist rule matches → **Skip**

3. **Data Sampling Check**
   - If file is whitelisted or passed blacklist checks
   - AND file extension matches `data_sampling.target_extensions`
   - AND data sampling is enabled → **Sample** instead of full copy

4. **Default Action**
   - If no rules match → **Copy** verbatim

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

## Exit Codes

- `0`: Success
- `1`: Error occurred
- `130`: Operation cancelled by user (Ctrl+C)

## Best Practices

1. **Always use dry run first** for new configurations:
   ```bash
   python repo_distiller.py ./source ./dest --dry-run --verbose
   ```

2. **Start with restrictive blacklists**, then whitelist exceptions

3. **Use glob patterns** for flexible matching

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
python repo_distiller.py ./source ./dest --dry-run --verbose | grep "filename"
```

### Permission errors
**Solution**: Ensure you have read access to source and write access to destination

## Advanced Usage

### Combining with Context Preparation Tools

The distiller is designed to work as part of an LLM context preparation pipeline:

```bash
# 1. Distill repository
python repo_distiller.py ./my-repo ./distilled

# 2. Generate context document for LLM
cat ./distilled/**/*.py > context_for_llm.txt
```

### Custom Sampling Logic

For specialized data formats, modify the `_sample_csv_file()` or `_sample_json_file()` methods in `repo_distiller.py`.

## Configuration Examples

### Example 1: Python Project
```yaml
ai_coding_env: 'chat'
max_file_size_mb: 5

whitelist:
  files:
    - "README.md"
    - "requirements.txt"
    - "setup.py"
    - "*.md"
  directories:
    - "src/"
    - "tests/"

blacklist:
  extensions:
    - ".pyc"
    - ".pyo"
    - ".egg-info"
  directories:
    - ".git/"
    - "__pycache__/"
    - "venv/"
    - ".pytest_cache/"

data_sampling:
  enabled: true
  target_extensions: [".csv", ".json"]
  head_rows: 10
  tail_rows: 10
```

### Example 2: JavaScript/Node.js Project
```yaml
ai_coding_env: 'ide'
max_file_size_mb: 3

whitelist:
  files:
    - "package.json"
    - "README.md"
    - "*.md"
  directories:
    - "src/"
    - "lib/"
    - "test/"

blacklist:
  files:
    - "package-lock.json"
    - "yarn.lock"
  directories:
    - "node_modules/"
    - ".git/"
    - "dist/"
    - "build/"
    - "coverage/"
  extensions:
    - ".min.js"
    - ".map"

data_sampling:
  enabled: false
```

### Example 3: Documentation Only
```yaml
ai_coding_env: 'chat'
max_file_size_mb: 10

whitelist:
  files:
    - "*.md"
    - "*.rst"
    - "*.txt"
  directories:
    - "docs/"

blacklist:
  directories:
    - ".git/"
  extensions:
    - ".pyc"
    - ".png"
    - ".jpg"
    - ".pdf"

data_sampling:
  enabled: false
```

## Glossary

- **Distillation**: The process of filtering a repository to create a lightweight copy
- **Whitelist**: Rules that force inclusion of files/directories (highest priority)
- **Blacklist**: Rules that exclude files/directories (unless whitelisted)
- **Glob Pattern**: A pattern with wildcards (* and **) for matching multiple files
- **Data Sampling**: Creating a partial copy of large data files (head + tail)
- **Dry Run**: Preview mode that shows actions without executing them

## Support

For technical details, see `docs/tech-specs.md`.

For issues or contributions, refer to the project repository.

## Version History

### v1.0.0 (2025-12-14)
- Initial release
- Core filtering engine
- Data sampling for CSV/JSON/JSONL
- Comprehensive logging
- Dry run mode
