# Repository Distiller - Technical Specification

This document provides comprehensive technical details for AI-assisted coding and maintenance of the Repository Distiller system.

**Version:** 1.0.0  
**Updated:** 2025-12-14  
**Package Manager:** uv  
**Module Location:** src/repo_distiller.py

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                CLI Interface (main)                          │
│  - Argument parsing (argparse)                              │
│  - Logging setup                                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          DistillerConfig (from YAML)                         │
│  - Configuration loading                                    │
│  - Validation and normalization                             │
│  - Regex pattern compilation                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│      RepositoryDistiller (Core Logic)                        │
│  - File system traversal                                    │
│  - Rule application (whitelist → blacklist → sampling)      │
│  - File processing (copy/sample/skip)                       │
│  - Statistics tracking                                      │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure

```
repo_distiller_project/
├── src/
│   └── repo_distiller.py      # Main executable module
├── config.yaml                # Configuration file
├── pyproject.toml             # uv project configuration
├── README.md                  # Project overview
├── LICENSE                    # MIT License
├── .gitignore                # Git ignore rules
├── docs/
│   ├── user-manual.md        # User documentation
│   └── tech-specs.md         # This file
├── logs/                      # Auto-generated log files
└── tests/                     # Future test suite
```

### Dependencies

**Runtime:**
- Python >=3.7
- PyYAML >=6.0.1

**Development (optional):**
- pytest >=7.0.0
- pytest-cov >=4.0.0
- black >=23.0.0
- mypy >=1.0.0
- ruff >=0.1.0

**Package Manager:** uv (recommended)

**Standard Library:**
- `argparse` - CLI argument parsing
- `logging` - Dual-stream logging
- `pathlib` - Path operations
- `shutil` - File operations
- `json`, `csv` - Data parsing
- `re` - Regex matching
- `datetime` - Timestamps
- `dataclasses` - Type-safe containers
- `enum` - Action enumeration

## Data Structures

### Enums

#### FilterAction
```python
class FilterAction(Enum):
    """Actions the distiller can take for a file."""
    COPY = "COPY"      # Copy file verbatim
    SAMPLE = "SAMPLE"  # Sample data file (head + tail)
    SKIP = "SKIP"      # Skip file entirely
```

### Dataclasses

#### FilterStats
```python
@dataclass
class FilterStats:
    """
    Statistics accumulator for distillation operations.

    Attributes:
        scanned (int): Total files scanned
        copied (int): Files copied verbatim
        sampled (int): Files sampled (partial copy)
        skipped (int): Files skipped
        errors (int): Errors encountered
        skipped_reasons (Dict[str, int]): Breakdown of skip reasons

    Methods:
        add_skip_reason(self, reason: str) -> None:
            Increment counter for a specific skip reason.
    """
    scanned: int = 0
    copied: int = 0
    sampled: int = 0
    skipped: int = 0
    errors: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)
```

#### DistillerConfig
```python
@dataclass
class DistillerConfig:
    """
    Configuration container loaded from YAML.

    Attributes:
        max_file_size_mb (float): Maximum file size threshold (applied after whitelist)
        whitelist_files (List[str]): Glob patterns for whitelisted files
        whitelist_directories (List[str]): Glob patterns for whitelisted dirs
        blacklist_files (List[str]): Glob patterns for blacklisted files
        blacklist_extensions (List[str]): File extensions to skip (normalized with dot)
        blacklist_patterns (List[re.Pattern]): Compiled regex patterns
        blacklist_directories (List[str]): Glob patterns for blacklisted dirs
        data_sampling_enabled (bool): Enable data file sampling
        data_sampling_extensions (Set[str]): Extensions for sampling (normalized)
        data_sampling_include_header (bool): Include CSV header in sample
        data_sampling_head_rows (int): Number of head rows/objects to sample
        data_sampling_tail_rows (int): Number of tail rows/objects to sample
        ai_coding_env (str): Target AI coding environment

    Methods:
        @staticmethod
        from_yaml(config_path: Path) -> 'DistillerConfig':
            Load and parse configuration from YAML file.

            Processing:
                1. Loads YAML with yaml.safe_load()
                2. Compiles regex patterns from strings
                3. Normalizes extensions (ensures leading dot)
                4. Normalizes sampling extensions
                5. Returns populated DistillerConfig instance

            Raises:
                FileNotFoundError: If config file doesn't exist
                ValueError: If YAML is invalid
    """
```

## Core Classes

### RepositoryDistiller

#### Class Signature
```python
class RepositoryDistiller:
    """
    Main distillation engine implementing filtering and processing logic.

    Attributes:
        config (DistillerConfig): Configuration instance
        logger (logging.Logger): Logger instance
        stats (FilterStats): Statistics tracker

    Methods:
        Public:
            __init__(config, logger)
            distill(source_dir, dest_dir, dry_run=False) -> bool
            determine_action(path, base_path) -> Tuple[FilterAction, Optional[str]]
            process_file(source, destination, action) -> bool

        Private:
            _matches_glob_pattern(path, patterns, base_path) -> bool
            _is_whitelisted(path, base_path) -> bool
            _is_blacklisted(path, base_path) -> Tuple[bool, Optional[str]]
            _should_sample_data_file(path) -> bool
            _sample_csv_file(source, destination) -> bool
            _sample_json_file(source, destination) -> bool
            _confirm_overwrite(dest_dir) -> bool
            _print_summary() -> None
    """
```

#### Public Methods

##### distill()
```python
def distill(self, source_dir: Path, dest_dir: Path, dry_run: bool = False) -> bool:
    """
    Main entry point: perform full repository distillation.

    Algorithm:
        1. Validate source directory exists and is a directory
        2. Prepare destination directory:
           - If exists: prompt user for confirmation, delete if confirmed
           - Create destination directory
        3. Walk source directory using Path.rglob('*')
        4. For each file (skip directories):
           a. Increment scanned counter
           b. Call determine_action(path, source_dir)
           c. If action is SKIP:
              - Add skip reason to stats
              - Log and continue
           d. Otherwise:
              - Calculate destination path (preserve relative structure)
              - If dry_run: log action, update stats
              - If not dry_run: call process_file()
        5. Print summary report
        6. Return success status (True if errors == 0)

    Args:
        source_dir (Path): Source repository path
        dest_dir (Path): Destination output path
        dry_run (bool): If True, simulate without actual file operations

    Returns:
        bool: True if successful (errors == 0), False otherwise

    Error Handling:
        - Validates source exists and is directory (logs error, returns False)
        - Catches all exceptions during traversal (logs error, returns False)
        - Individual file errors don't stop processing (logged, counted)

    Side Effects:
        - Creates/deletes directories
        - Copies/samples files
        - Updates self.stats
        - Logs extensively
    """
```

##### determine_action()
```python
def determine_action(self, path: Path, base_path: Path) -> Tuple[FilterAction, Optional[str]]:
    """
    Apply rule priority logic to determine action for a path.

    Rule Application Order (CRITICAL):
        1. Whitelist check (_is_whitelisted)
           - If whitelisted:
             - Check if should sample (_should_sample_data_file)
             - Return (SAMPLE, None) or (COPY, None)
           - If NOT whitelisted:
             - Skip to step 4 (whitelist-only mode)

        2. Blacklist check (_is_blacklisted) - only if whitelisted
           - Checks: file size, specific files, directories, extensions, patterns
           - If blacklisted: return (SKIP, reason)

        3. Data sampling check - only if whitelisted and not blacklisted
           - If data file: return (SAMPLE, None)

        4. Default action
           - If reached here and whitelisted: return (COPY, None)
           - If not whitelisted: return (SKIP, "not_whitelisted")

    Args:
        path (Path): Path to evaluate
        base_path (Path): Repository root for relative path calculations

    Returns:
        Tuple[FilterAction, Optional[str]]:
            - FilterAction: COPY, SAMPLE, or SKIP
            - str or None: Skip reason (only if SKIP)

    Examples:
        Whitelisted file:
            >>> determine_action(Path("src/main.py"), Path("."))
            (FilterAction.COPY, None)

        Whitelisted data file:
            >>> determine_action(Path("data/samples.csv"), Path("."))
            (FilterAction.SAMPLE, None)

        Versioned file in whitelisted dir:
            >>> determine_action(Path("src/script_v1.py"), Path("."))
            (FilterAction.SKIP, "blacklist_pattern:_v\d{1,2}\.py$")

        Not whitelisted:
            >>> determine_action(Path("random/file.py"), Path("."))
            (FilterAction.SKIP, "not_whitelisted")
    """
```

##### process_file()
```python
def process_file(self, source: Path, destination: Path, action: FilterAction) -> bool:
    """
    Execute the determined action on a file.

    Actions:
        COPY:
            - Use shutil.copy2() to preserve metadata
            - Increment copied counter
            - Log at DEBUG level

        SAMPLE:
            - Determine file type from extension
            - Delegate to:
              - _sample_csv_file() for .csv, .tsv
              - _sample_json_file() for .json, .jsonl
              - Copy as-is for unknown types (with warning)
            - Increment sampled counter on success
            - Increment error counter on failure

        SKIP:
            - Log at DEBUG level
            - Increment skipped counter
            - Return True (not an error)

    Args:
        source (Path): Source file path
        destination (Path): Destination file path
        action (FilterAction): Action to perform

    Returns:
        bool: True if successful, False if error occurred

    Side Effects:
        - Creates parent directories for destination
        - Modifies self.stats counters
        - Logs action

    Error Handling:
        - Wraps all operations in try-except
        - Logs full error with traceback
        - Increments error counter
        - Returns False on any exception
    """
```

#### Private Methods

##### _matches_glob_pattern()
```python
def _matches_glob_pattern(self, path: Path, patterns: List[str], base_path: Path) -> bool:
    """
    Check if a path matches any glob pattern in the list.

    Matching Logic:
        1. Convert path to relative path from base_path
        2. For each pattern:
           a. Normalize pattern (strip ./ and trailing /)
           b. Check direct string match
           c. Check directory prefix match (for directory patterns)
           d. Check if file is within directory pattern
           e. Check glob pattern match using Path.match()

    Glob Pattern Support:
        - '*' matches any characters within a filename/directory
        - '**' matches any directories recursively
        - '?' matches a single character

    Args:
        path (Path): Absolute path to check
        patterns (List[str]): List of glob patterns (relative to repo root)
        base_path (Path): Repository root

    Returns:
        bool: True if path matches any pattern

    Examples:
        Pattern "src/" matches:
          ✓ src/ (directory)
          ✓ src/main.py (file in directory)
          ✓ src/utils/helper.py (nested file)

        Pattern "*.md" matches:
          ✓ README.md
          ✓ docs/guide.md

        Pattern "data/**/*.csv" matches:
          ✓ data/train.csv
          ✓ data/subset/test.csv
    """
```

##### _is_blacklisted()
```python
def _is_blacklisted(self, path: Path, base_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Check if path is blacklisted and return reason.

    Check Order:
        1. File size (if file and size > max_file_size_mb)
           -> return (True, "file_size>XMB")

        2. Specific file blacklist (_matches_glob_pattern with blacklist_files)
           -> return (True, "blacklist_file")

        3. Directory blacklist (_matches_glob_pattern with blacklist_directories)
           -> return (True, "blacklist_directory")

        4. Extension blacklist (path.suffix in blacklist_extensions)
           -> return (True, "blacklist_ext:.xxx")

        5. Regex pattern blacklist (pattern.search(filename) for each pattern)
           -> return (True, "blacklist_pattern:PATTERN")

        6. If none match: return (False, None)

    Args:
        path (Path): Path to check
        base_path (Path): Repository root

    Returns:
        Tuple[bool, Optional[str]]:
            - bool: True if blacklisted
            - str: Reason string (e.g., "blacklist_pattern:_v\d{1,2}\.py$")

    Reason String Format:
        - "file_size>XMB" - File exceeds size limit
        - "blacklist_file" - Matches blacklist_files pattern
        - "blacklist_directory" - In blacklisted directory
        - "blacklist_ext:.xxx" - Has blacklisted extension
        - "blacklist_pattern:REGEX" - Matches regex pattern
    """
```

##### _sample_csv_file()
```python
def _sample_csv_file(self, source: Path, destination: Path) -> bool:
    """
    Sample a CSV/TSV file using Python csv module.

    Algorithm:
        1. Open source with csv.reader(), encoding='utf-8', errors='replace'
        2. Read all rows into memory: all_rows = list(reader)
        3. Handle empty file: log warning, copy as-is, return True
        4. Separate header and data:
           - If include_header: header_rows = [all_rows[0]], data starts at index 1
           - Otherwise: no header, data starts at index 0
        5. Check if sampling needed:
           - If total_data_rows <= (head_rows + tail_rows): copy all rows
           - Otherwise: sample head and tail
        6. Write sampled file:
           - Write header (if applicable)
           - Write first head_rows
           - Write separator row: ["... (N rows omitted) ..."]
           - Write last tail_rows
        7. Log sampling action with row count
        8. Return True

    Args:
        source (Path): Source CSV file
        destination (Path): Destination file

    Returns:
        bool: True if successful, False on error

    Error Handling:
        - Uses 'errors=replace' for encoding issues
        - Catches all exceptions, logs error, returns False

    Performance Note:
        - Loads entire file into memory
        - For very large files (GB+), consider streaming implementation

    Example Output (CSV with 100 rows, head_rows=5, tail_rows=5):
        header
        row1
        row2
        row3
        row4
        row5
        ... (90 rows omitted) ...
        row96
        row97
        row98
        row99
        row100
    """
```

##### _sample_json_file()
```python
def _sample_json_file(self, source: Path, destination: Path) -> bool:
    """
    Sample a JSON/JSONL file.

    JSONL Handling (.jsonl):
        1. Read file content
        2. Split on newlines, filter empty lines
        3. If total <= (head + tail): copy as-is
        4. Otherwise:
           - Extract head lines
           - Extract tail lines
           - Write: head + separator + tail
        5. Log sampling action

    JSON Handling (.json):
        1. Read file content
        2. Parse with json.loads()
        3. Handle parse errors: log warning, copy as-is
        4. If root is array:
           - If len <= (head + tail): copy as-is
           - Otherwise: create sampled object:
             {
               "_sampled": true,
               "_total_items": N,
               "_omitted_items": M,
               "head": [first items],
               "tail": [last items]
             }
        5. If root is object/primitive: copy as-is
        6. Log sampling action

    Args:
        source (Path): Source JSON/JSONL file
        destination (Path): Destination file

    Returns:
        bool: True if successful, False on error

    Error Handling:
        - Invalid JSON: logs warning, copies as-is
        - Uses 'errors=replace' for encoding issues
        - Catches all exceptions, logs error, returns False

    Example Output (JSON array with 50 items, head=5, tail=5):
        {
          "_sampled": true,
          "_total_items": 50,
          "_omitted_items": 40,
          "head": [item1, item2, item3, item4, item5],
          "tail": [item46, item47, item48, item49, item50]
        }
    """
```

## Functions

### setup_logging()
```python
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """
    Configure dual-stream logging (console + file).

    Implementation:
        1. Create log_dir if doesn't exist
        2. Generate timestamp: YYYYMMDD_HHMMSS
        3. Create log file: log_{timestamp}.txt
        4. Create logger: 'repo_distiller'
        5. Set logger level: DEBUG if verbose else INFO
        6. Add console handler:
           - Format: "LEVEL    | message"
           - Level: DEBUG if verbose else INFO
           - Stream: stdout
        7. Add file handler:
           - Format: "timestamp | LEVEL | function_name | message"
           - Level: DEBUG (always)
           - Encoding: UTF-8

    Args:
        log_dir (Path): Directory for log files
        verbose (bool): Enable DEBUG level on console

    Returns:
        logging.Logger: Configured logger instance

    Usage in Code:
        logger.debug("Detailed info for debugging")
        logger.info("User-facing progress info")
        logger.warning("Recoverable issue")
        logger.error("Error that doesn't stop execution")
        logger.exception("Fatal error with traceback")
    """
```

### parse_arguments()
```python
def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate CLI arguments using argparse.

    Arguments:
        Positional:
            source_dir (Path): Source repository directory
            destination_dir (Path): Destination directory

        Optional:
            -c, --config (Path): Config file path (default: ./config.yaml)
            -d, --dry-run (flag): Preview mode
            -v, --verbose (flag): Enable DEBUG logging
            --log-dir (Path): Log directory (default: ./logs)
            --version (flag): Print version and exit

    Validation:
        - If not dry_run: checks source_dir exists
        - Provides helpful error messages via parser.error()

    Returns:
        argparse.Namespace with attributes:
            - source_dir (Path)
            - destination_dir (Path)
            - config (Path)
            - dry_run (bool)
            - verbose (bool)
            - log_dir (Path)
    """
```

### main()
```python
def main() -> int:
    """
    Main entry point coordinating the distillation workflow.

    Workflow:
        1. Parse CLI arguments (parse_arguments)
        2. Setup logging (setup_logging)
        3. Load configuration (DistillerConfig.from_yaml)
        4. Create distiller instance (RepositoryDistiller)
        5. Execute distillation (distiller.distill)
        6. Log final status
        7. Return exit code

    Returns:
        int: Exit code
            0 - Success
            1 - Error occurred
            130 - User cancelled (Ctrl+C)

    Error Handling:
        - KeyboardInterrupt: logs "cancelled by user", returns 130
        - All other exceptions: logs with traceback, returns 1

    Entry Point:
        if __name__ == '__main__':
            sys.exit(main())
    """
```

## Configuration File Format

### YAML Schema
```yaml
# Type: str, Options: ['chat', 'ide', 'agentic', 'cli']
ai_coding_env: 'chat'

# Type: float, Unit: megabytes (applied after whitelist check)
max_file_size_mb: 5

# WHITELIST (required for inclusion - whitelist-only mode)
whitelist:
  files: List[str]        # Glob patterns
  directories: List[str]  # Glob patterns

# BLACKLIST (excludes from whitelisted items)
blacklist:
  files: List[str]        # Glob patterns
  extensions: List[str]   # Leading dot normalized automatically
  patterns: List[str]     # Python regex patterns (raw strings)
  directories: List[str]  # Glob patterns

# DATA SAMPLING
data_sampling:
  enabled: bool
  target_extensions: List[str]  # Leading dot normalized
  include_header: bool
  head_rows: int
  tail_rows: int
```

### Regex Pattern Guidelines

**Python Regex Syntax:**
- Use raw strings in YAML: `"pattern"`
- Escape backslashes: `\d` not `\d`
- Anchor patterns: `^` (start), `$` (end)

**Common Patterns:**
```yaml
patterns:
  # Versioned files: *_v1.py, *_v2.py, ..., *_v99.py
  - "_v\d{1,2}\.py$"

  # Step files: step1_*, step2_*, ..., step99_*
  - "^step\d{1,2}"

  # Utility files: utils_*.py
  - "^utils_"

  # Backup files: *_backup.*, *_backup1.*, etc.
  - "_backup\d*\."

  # Temporary files: *.bak
  - "\.bak$"

  # Tilde backups: file.txt~
  - "~$"
```

## Testing Strategy

### Unit Tests (Future)
```python
# tests/test_filter_logic.py
def test_whitelist_overrides_blacklist()
def test_not_whitelisted_is_skipped()  # NEW: whitelist-only mode
def test_versioned_file_filtered()     # NEW: regex patterns
def test_step_file_filtered()          # NEW: regex patterns
def test_file_size_applied_after_whitelist()
def test_data_sampling_csv()
def test_data_sampling_jsonl()
def test_glob_pattern_matching()
def test_regex_pattern_matching()      # NEW

# tests/test_config.py
def test_config_loading()
def test_regex_compilation()            # NEW
def test_invalid_yaml()
def test_missing_config_file()

# tests/test_integration.py
def test_full_distillation_workflow()
def test_whitelist_only_mode()          # NEW
def test_dry_run_mode()
```

## Debugging Guide

### Common Issues

**Issue**: Versioned files not being filtered
```bash
# Solution: Check regex pattern compilation
uv run python -c "
import re
pattern = re.compile(r'_v\d{1,2}\.py$')
print(pattern.search('script_v1.py'))  # Should match
"
```

**Issue**: Files in whitelisted directory not copied
```bash
# Solution: Check for blacklist patterns
uv run python src/repo_distiller.py ./source ./dest --verbose --dry-run | grep "SKIP"
```

**Issue**: Data files not being sampled
```bash
# Solution: Verify extension matches target_extensions in config
cat config.yaml | grep -A5 "target_extensions"
```

### Strategic Debug Points

Key locations for adding debug statements:
1. `determine_action()` - Line before "Step 1: Whitelist check"
2. `_matches_glob_pattern()` - Before pattern loop
3. `_is_blacklisted()` - Before each check type
4. `process_file()` - Before action switch

## Running the Tool

### With uv (Recommended)
```bash
# From project root
uv run python src/repo_distiller.py <source> <dest> [options]

# Development mode
uv sync --all-extras
uv run python src/repo_distiller.py <source> <dest>
```

### Without uv
```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install pyyaml

# Run
python src/repo_distiller.py <source> <dest> [options]
```

## Performance Considerations

- **File Traversal**: Iterator-based with Path.rglob('*') - minimal memory
- **Data Sampling**: Loads files into memory (acceptable for < max_size_mb)
- **Regex Matching**: Compiled patterns cached in config
- **Typical Speed**: 500-1000 files/second (I/O dependent)

## Extension Points

### Adding Custom Patterns

To filter additional file types:

```yaml
# config.yaml
blacklist:
  patterns:
    - "your_custom_pattern"
```

Test pattern:
```python
import re
pattern = re.compile(r"your_custom_pattern")
print(pattern.search("test_filename.py"))
```

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-14  
**Optimized for**: AI-assisted coding with uv package manager
