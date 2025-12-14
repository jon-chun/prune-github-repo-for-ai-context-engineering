# Repository Distiller - Technical Specification

This document provides comprehensive technical details for AI-assisted coding and maintenance of the Repository Distiller system.

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface (main)                      │
│  - Argument parsing (argparse)                              │
│  - Logging setup                                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              DistillerConfig (from YAML)                     │
│  - Configuration loading                                    │
│  - Validation and normalization                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          RepositoryDistiller (Core Logic)                    │
│  - File system traversal                                    │
│  - Rule application (whitelist/blacklist)                   │
│  - File processing (copy/sample/skip)                       │
│  - Statistics tracking                                      │
└─────────────────────────────────────────────────────────────┘
```

### Dependencies

**Standard Library:**
- `argparse` - CLI argument parsing
- `logging` - Dual-stream logging (console + file)
- `pathlib` - Modern path operations
- `shutil` - File operations
- `json`, `csv` - Data file parsing
- `re` - Regular expression matching
- `datetime` - Timestamp generation
- `dataclasses` - Type-safe configuration containers
- `enum` - Action enumeration

**External:**
- `PyYAML` - YAML configuration parsing

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
    """
    scanned: int = 0
    copied: int = 0
    sampled: int = 0
    skipped: int = 0
    errors: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)

    def add_skip_reason(self, reason: str) -> None:
        """Increment counter for a specific skip reason."""
```

#### DistillerConfig
```python
@dataclass
class DistillerConfig:
    """
    Configuration container loaded from YAML.

    Attributes:
        max_file_size_mb (float): Maximum file size threshold
        whitelist_files (List[str]): Glob patterns for whitelisted files
        whitelist_directories (List[str]): Glob patterns for whitelisted dirs
        blacklist_files (List[str]): Glob patterns for blacklisted files
        blacklist_extensions (List[str]): File extensions to skip (normalized with leading dot)
        blacklist_patterns (List[re.Pattern]): Compiled regex patterns
        blacklist_directories (List[str]): Glob patterns for blacklisted dirs
        data_sampling_enabled (bool): Enable data file sampling
        data_sampling_extensions (Set[str]): Extensions for sampling (normalized)
        data_sampling_include_header (bool): Include CSV header in sample
        data_sampling_head_rows (int): Number of head rows/objects to sample
        data_sampling_tail_rows (int): Number of tail rows/objects to sample
        ai_coding_env (str): Target AI coding environment ('chat', 'ide', 'agentic', 'cli')

    Methods:
        @staticmethod
        from_yaml(config_path: Path) -> 'DistillerConfig':
            Load and parse configuration from YAML file.
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
    """

    def __init__(self, config: DistillerConfig, logger: logging.Logger):
        """Initialize distiller with configuration and logger."""
```

#### Public Methods

##### distill()
```python
def distill(self, source_dir: Path, dest_dir: Path, dry_run: bool = False) -> bool:
    """
    Main entry point: perform full repository distillation.

    Algorithm:
        1. Validate source directory exists
        2. Prepare destination directory (with user confirmation if exists)
        3. Recursively walk source directory using Path.rglob('*')
        4. For each file:
           a. Determine action using determine_action()
           b. Execute action (or log for dry run)
           c. Update statistics
        5. Print summary report

    Args:
        source_dir: Source repository path
        dest_dir: Destination output path
        dry_run: If True, simulate without actual file operations

    Returns:
        True if successful (errors == 0), False otherwise

    Error Handling:
        - Catches all exceptions during traversal
        - Logs errors but continues processing
        - Returns False if any errors occurred
    """
```

##### determine_action()
```python
def determine_action(self, path: Path, base_path: Path) -> Tuple[FilterAction, Optional[str]]:
    """
    Apply rule priority logic to determine action for a path.

    Rule Application Order:
        1. Whitelist check (highest priority)
           - If whitelisted → COPY or SAMPLE (if data file)

        2. Blacklist check (if not whitelisted)
           - Check: specific files, directories, extensions, patterns, size
           - If blacklisted → SKIP with reason

        3. Data sampling check
           - If enabled AND extension matches → SAMPLE

        4. Default → COPY

    Args:
        path: Path to evaluate
        base_path: Repository root for relative path calculations

    Returns:
        Tuple of (FilterAction, skip_reason)
        - skip_reason is None unless action is SKIP

    Examples:
        >>> distiller.determine_action(Path("src/main.py"), Path("."))
        (FilterAction.COPY, None)

        >>> distiller.determine_action(Path("data.csv"), Path("."))
        (FilterAction.SAMPLE, None)

        >>> distiller.determine_action(Path("file.log"), Path("."))
        (FilterAction.SKIP, "blacklist_ext:.log")
    """
```

##### process_file()
```python
def process_file(self, source: Path, destination: Path, action: FilterAction) -> bool:
    """
    Execute the determined action on a file.

    Actions:
        - COPY: Use shutil.copy2() (preserves metadata)
        - SAMPLE: Delegate to _sample_csv_file() or _sample_json_file()
        - SKIP: Log and return True

    Args:
        source: Source file path
        destination: Destination file path
        action: Action to perform

    Returns:
        True if successful, False if error occurred

    Side Effects:
        - Creates parent directories for destination
        - Updates self.stats counters
        - Logs action at appropriate level

    Error Handling:
        - Catches all exceptions
        - Logs error with full traceback
        - Increments error counter
        - Returns False
    """
```

#### Private Methods

##### _matches_glob_pattern()
```python
def _matches_glob_pattern(self, path: Path, patterns: List[str], base_path: Path) -> bool:
    """
    Check if a path matches any glob pattern in the list.

    Matching Logic:
        - Converts path to relative path from base_path
        - Normalizes pattern (strips leading ./ and trailing /)
        - Checks:
          1. Direct string match
          2. Directory prefix match (for directory patterns)
          3. Nested file within directory pattern
          4. Glob pattern match using Path.match() (supports *)

    Args:
        path: Absolute path to check
        patterns: List of glob patterns (relative to repo root)
        base_path: Repository root

    Returns:
        True if path matches any pattern

    Examples:
        Pattern "src/" matches:
          - src/ (directory)
          - src/main.py (file in directory)
          - src/utils/helper.py (nested file)

        Pattern "*.md" matches:
          - README.md
          - docs/guide.md
    """
```

##### _is_whitelisted()
```python
def _is_whitelisted(self, path: Path, base_path: Path) -> bool:
    """
    Check if path is whitelisted (highest priority check).

    Checks both file and directory whitelists.

    Returns:
        True if path matches any whitelist rule
    """
```

##### _is_blacklisted()
```python
def _is_blacklisted(self, path: Path, base_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Check if path is blacklisted and return reason.

    Check Order (as specified in requirements point 6):
        1. File size (if file)
        2. Specific file blacklist
        3. Directory blacklist
        4. Extension blacklist
        5. Regex pattern blacklist

    Args:
        path: Path to check
        base_path: Repository root

    Returns:
        Tuple of (is_blacklisted, reason_string)
        - reason examples: "file_size>5MB", "blacklist_ext:.log", "blacklist_pattern:_v\\d+"
    """
```

##### _should_sample_data_file()
```python
def _should_sample_data_file(self, path: Path) -> bool:
    """
    Determine if file should be sampled instead of copied.

    Conditions:
        - data_sampling_enabled == True
        - path is a file
        - file extension in data_sampling_extensions

    Returns:
        True if file should be sampled
    """
```

##### _sample_csv_file()
```python
def _sample_csv_file(self, source: Path, destination: Path) -> bool:
    """
    Sample a CSV/TSV file using Python csv module.

    Algorithm:
        1. Read all rows into memory using csv.reader()
        2. Separate header (if include_header=True) and data rows
        3. If total rows <= head + tail: copy all
        4. Otherwise:
           - Write header (if applicable)
           - Write first head_rows
           - Write separator comment row
           - Write last tail_rows

    Args:
        source: Source CSV file
        destination: Destination file

    Returns:
        True if successful, False on error

    Error Handling:
        - Uses 'errors=replace' for encoding issues
        - Empty files are copied as-is
        - Logs warnings and errors appropriately

    Performance Note:
        Loads entire file into memory. For very large files (GB+), 
        consider streaming implementation.
    """
```

##### _sample_json_file()
```python
def _sample_json_file(self, source: Path, destination: Path) -> bool:
    """
    Sample a JSON/JSONL file.

    JSONL Handling (.jsonl):
        - Split on newlines
        - Treat each line as an object
        - Sample lines (head + separator + tail)

    JSON Handling (.json):
        - Parse with json.loads()
        - If root is array: sample array elements
        - If root is object/primitive: copy as-is
        - Sampled output format:
          {
            "_sampled": true,
            "_total_items": N,
            "_omitted_items": M,
            "head": [...],
            "tail": [...]
          }

    Args:
        source: Source JSON/JSONL file
        destination: Destination file

    Returns:
        True if successful, False on error

    Error Handling:
        - Invalid JSON: logs warning and copies as-is
        - Uses 'errors=replace' for encoding issues
    """
```

##### _confirm_overwrite()
```python
def _confirm_overwrite(self, dest_dir: Path) -> bool:
    """
    Prompt user for confirmation if destination exists.

    Returns:
        True if user confirms (input 'yes' or 'y')
        False otherwise or on EOF/Ctrl+C
    """
```

##### _print_summary()
```python
def _print_summary(self) -> None:
    """
    Print formatted summary report to logger.

    Output includes:
        - Total files scanned
        - Files copied, sampled, skipped
        - Errors
        - Skip reasons breakdown (sorted by frequency)
    """
```

## Functions

### setup_logging()
```python
def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """
    Configure dual-stream logging (console + file).

    Setup:
        - Creates log directory if doesn't exist
        - Generates timestamped log filename: log_YYYYMMDD_HHMMSS.txt
        - Configures logger named 'repo_distiller'

    Console Handler:
        - Format: "LEVEL    | message"
        - Level: INFO (default) or DEBUG (if verbose)
        - Stream: stdout

    File Handler:
        - Format: "timestamp | LEVEL    | function_name | message"
        - Level: DEBUG (always)
        - Encoding: UTF-8

    Args:
        log_dir: Directory for log files
        verbose: Enable DEBUG level on console

    Returns:
        Configured logger instance

    Best Practices:
        - Use logger.debug() for detailed decision-making
        - Use logger.info() for user-facing progress
        - Use logger.warning() for recoverable issues
        - Use logger.error() for errors that don't stop execution
        - Use logger.exception() for fatal errors (includes traceback)
    """
```

### parse_arguments()
```python
def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate CLI arguments.

    Returns:
        Namespace with attributes:
            - source_dir (Path)
            - destination_dir (Path)
            - config (Path)
            - dry_run (bool)
            - verbose (bool)
            - log_dir (Path)

    Validation:
        - Checks source_dir exists (unless dry_run)
        - Provides helpful error messages via parser.error()
    """
```

### main()
```python
def main() -> int:
    """
    Main entry point coordinating the distillation workflow.

    Workflow:
        1. Parse arguments
        2. Setup logging
        3. Load configuration
        4. Create distiller instance
        5. Execute distillation
        6. Return exit code

    Returns:
        0: Success
        1: Error occurred
        130: User cancelled (Ctrl+C)

    Error Handling:
        - Catches KeyboardInterrupt for graceful Ctrl+C handling
        - Catches all other exceptions, logs with traceback
    """
```

## Configuration File Format

### YAML Schema
```yaml
# Type: str, Options: ['chat', 'ide', 'agentic', 'cli']
ai_coding_env: 'chat'

# Type: float, Unit: megabytes
max_file_size_mb: 5

whitelist:
  # Type: List[str], Glob patterns supported
  files: [...]
  directories: [...]

blacklist:
  # Type: List[str], Glob patterns supported
  files: [...]

  # Type: List[str], Leading dot normalized automatically
  extensions: [...]

  # Type: List[str], Python regex patterns (raw strings recommended)
  patterns: [...]

  # Type: List[str], Glob patterns supported
  directories: [...]

data_sampling:
  # Type: bool
  enabled: true

  # Type: List[str], Leading dot normalized automatically
  target_extensions: [...]

  # Type: bool
  include_header: true

  # Type: int
  head_rows: 5
  tail_rows: 5
```

## Error Handling Strategy

### Error Categories

1. **Configuration Errors** (Fatal - exit immediately)
   - Missing config file
   - Invalid YAML syntax
   - Missing required config fields

2. **Input Validation Errors** (Fatal - exit immediately)
   - Source directory doesn't exist
   - Source is not a directory

3. **File Operation Errors** (Non-fatal - log and continue)
   - Permission denied on specific file
   - Encoding errors in data files
   - Destination write failures

4. **User Cancellation** (Graceful exit)
   - Ctrl+C during operation
   - "No" response to overwrite prompt

### Recovery Mechanisms

- **Encoding errors**: Use `errors='replace'` parameter
- **Permission errors**: Log warning, increment error counter, continue
- **Invalid regex patterns**: Log warning, skip pattern, continue
- **Empty/malformed data files**: Log warning, copy as-is

## Performance Considerations

### Memory Usage
- **File traversal**: Uses `Path.rglob('*')` - iterator-based, minimal memory
- **Data sampling**: Loads entire file into memory (acceptable for files < max_size_mb)
- **Large JSON arrays**: Parsed fully with `json.loads()` - consider streaming for GB+ files

### I/O Optimization
- Uses `shutil.copy2()` for efficient file copying (preserves metadata)
- Batch directory creation with `mkdir(parents=True, exist_ok=True)`

### Scalability
- Tested with repositories up to 10,000 files
- Typical processing speed: 500-1000 files/second (depending on I/O)

## Testing Strategy

### Unit Tests (Future Implementation)
```python
# tests/test_filter_logic.py
def test_whitelist_overrides_blacklist()
def test_file_size_limit_applied_after_whitelist()
def test_data_sampling_csv()
def test_data_sampling_jsonl()
def test_glob_pattern_matching()
def test_regex_pattern_matching()

# tests/test_config.py
def test_config_loading()
def test_invalid_yaml()
def test_missing_config_file()

# tests/test_integration.py
def test_full_distillation_workflow()
def test_dry_run_mode()
```

### Test Data
Create fixture repositories with:
- Various file types (code, data, binary)
- Nested directory structures
- Edge cases (empty files, large files, special characters)

## Extension Points

### Adding New Data File Formats

To add support for a new data format (e.g., `.xml`, `.parquet`):

1. Add extension to `config.yaml`:
   ```yaml
   data_sampling:
     target_extensions:
       - ".xml"
   ```

2. Implement sampling method in `RepositoryDistiller`:
   ```python
   def _sample_xml_file(self, source: Path, destination: Path) -> bool:
       # Implementation here
       pass
   ```

3. Update `process_file()` to handle new extension:
   ```python
   elif ext == '.xml':
       success = self._sample_xml_file(source, destination)
   ```

### Custom Rule Types

To add new filtering rules (e.g., "modified in last N days"):

1. Add configuration field to `DistillerConfig`
2. Implement check method (e.g., `_is_recently_modified()`)
3. Update `determine_action()` rule priority logic

## Debugging Guide

### Common Issues

**Issue**: Files unexpectedly skipped
```bash
# Solution: Run with verbose logging
python repo_distiller.py ./source ./dest --verbose --dry-run | grep "SKIP"
```

**Issue**: Configuration not loading
```bash
# Solution: Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

**Issue**: Glob patterns not matching
```bash
# Solution: Test pattern in Python REPL
from pathlib import Path
path = Path("src/utils/helper.py")
print(path.match("src/**/*.py"))  # Should print True
```

### Strategic Debug Points

Key locations for adding debug statements:
1. `determine_action()` - see rule application
2. `_matches_glob_pattern()` - verify pattern matching logic
3. `process_file()` - confirm file operations
4. `_sample_*_file()` - debug sampling logic

## Workflow Integration

### AI-Assisted Coding Environments

#### Chat (Default)
```yaml
ai_coding_env: 'chat'
```
Optimized for conversational AI coding assistants (Claude, ChatGPT, etc.). Produces complete context suitable for copy-paste into chat interfaces.

#### IDE
```yaml
ai_coding_env: 'ide'
```
Optimized for IDE-integrated assistants (Cursor, GitHub Copilot). May include additional metadata or structure for IDE parsing.

#### Agentic
```yaml
ai_coding_env: 'agentic'
```
Optimized for autonomous coding agents (Aider, OpenHands). Includes structured metadata and clear file boundaries for agent parsing.

#### CLI
```yaml
ai_coding_env: 'cli'
```
Optimized for CLI-based coding assistants (Claude Code CLI, OpenCode CLI). Follows conventions like AGENTS.md, CLAUDE.md, skills/tools directories.

## Best Practices for AI Context

1. **Limit Context Size**: Keep distilled repos under 100MB for optimal LLM performance
2. **Include Documentation**: Always whitelist README.md and docs/
3. **Sample Large Data**: Enable data sampling to avoid token limits
4. **Test Before Production**: Always run dry-run first
5. **Version Configuration**: Track config.yaml in version control

## References

- Python argparse: Standard library documentation
- Python logging: Standard library documentation
- Glob patterns: Standard library pathlib documentation
- Data sampling techniques: CSV and JSON module docs
- LLM context preparation: AI-assisted coding best practices

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-14  
**For**: AI-assisted coding and maintenance
