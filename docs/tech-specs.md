# Repository Distiller - Technical Specification

**Version:** 1.0.1 (Path Resolution Fix)  
**Updated:** 2025-12-14  
**Module Location:** src/repo_distiller.py

## Version History

### v1.0.1 (2025-12-14) - Path Resolution Fix
**Critical Bug Fix:**
- **Issue:** Using relative paths like `../project-name` caused errors:
  ```
  '../project-name/file.py' is not in the subpath of '/current/working/dir'
  ```
- **Root Cause:** Paths weren't resolved to absolute paths before `Path.relative_to()` operations
- **Fix:** Added `.resolve()` calls to convert all paths to absolute:
  - In `parse_arguments()`: resolve source_dir, destination_dir, config, log_dir
  - In `distill()`: resolve source_dir and dest_dir at method entry
  - In path operations: ensure absolute paths before relative_to()

**Changed Methods:**
- `parse_arguments()` - Added path resolution for all arguments
- `distill()` - Resolves paths to absolute at entry point
- `_matches_glob_pattern()` - Added resolve() calls with comments
- `_sample_csv_file()` - Added resolve() calls
- `_sample_json_file()` - Added resolve() calls
- `process_file()` - Added resolve() calls

### v1.0.0 (2025-12-14)
- Initial release

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                CLI Interface (main)                          │
│  - Argument parsing (argparse)                              │
│  - Path resolution (NEW in v1.0.1)                          │
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
│  - Path resolution (NEW in v1.0.1)                          │
│  - Statistics tracking                                      │
└─────────────────────────────────────────────────────────────┘
```

## Critical Path Resolution Implementation

### Problem Statement
Python's `Path.relative_to()` requires both paths to be in the same resolution state (both relative or both absolute). Using relative paths like `../project` with `Path.cwd()` caused:

```
ValueError: '../project/file.py' is not in the subpath of '/absolute/path'
```

### Solution
All paths are resolved to absolute paths using `.resolve()` before any relative path operations:

```python
# In parse_arguments():
args.source_dir = args.source_dir.resolve()
args.destination_dir = args.destination_dir.resolve()
args.config = args.config.resolve()
args.log_dir = args.log_dir.resolve()

# In distill():
source_dir = source_dir.resolve()
dest_dir = dest_dir.resolve()

# In _matches_glob_pattern():
path = path.resolve()
base_path = base_path.resolve()
rel_path = path.relative_to(base_path)  # Now works!
```

## Key Classes

### FilterAction (Enum)
```python
class FilterAction(Enum):
    COPY = "COPY"      # Copy file verbatim
    SAMPLE = "SAMPLE"  # Sample data file (head + tail)
    SKIP = "SKIP"      # Skip file entirely
```

### FilterStats (Dataclass)
```python
@dataclass
class FilterStats:
    scanned: int = 0
    copied: int = 0
    sampled: int = 0
    skipped: int = 0
    errors: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)
```

### RepositoryDistiller (Main Engine)

**Public Methods:**
- `distill(source_dir, dest_dir, dry_run)` - Main entry point (v1.0.1: resolves paths)
- `determine_action(path, base_path)` - Apply filtering rules
- `process_file(source, destination, action)` - Execute action (v1.0.1: resolves paths)

**Private Methods:**
- `_matches_glob_pattern()` - Glob pattern matching (v1.0.1: resolves paths)
- `_is_whitelisted()` - Whitelist check
- `_is_blacklisted()` - Blacklist check with reason
- `_should_sample_data_file()` - Data sampling check
- `_sample_csv_file()` - CSV sampling (v1.0.1: resolves paths)
- `_sample_json_file()` - JSON/JSONL sampling (v1.0.1: resolves paths)

## Configuration File Format

### YAML Schema

```yaml
ai_coding_env: str  # 'chat', 'ide', 'agentic', 'cli'
max_file_size_mb: float

whitelist:
  files: List[str]        # Glob patterns
  directories: List[str]  # Glob patterns

blacklist:
  files: List[str]        # Glob patterns
  extensions: List[str]   # Leading dot normalized
  patterns: List[str]     # Python regex (use single quotes!)
  directories: List[str]  # Glob patterns

data_sampling:
  enabled: bool
  target_extensions: List[str]
  include_header: bool
  head_rows: int
  tail_rows: int
```

### Regex Pattern Guidelines

**CRITICAL:** Use **single quotes** for regex patterns in YAML:

```yaml
# ✅ CORRECT
patterns:
  - '_v\d{1,2}\.py$'
  - '^step\d{1,2}'
  - '^utils_'

# ❌ WRONG - causes YAML parsing error
patterns:
  - "_v\d{1,2}\.py$"  # ERROR: unknown escape character 'd'
```

## Running the Tool

### With uv (Recommended)
```bash
# From project root - now works with relative paths!
uv run python src/repo_distiller.py ../source ./dest [options]

# Development mode
uv sync --all-extras
```

### Without uv
```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install pyyaml

# Run
python src/repo_distiller.py ../source ./dest [options]
```

## Debugging Common Issues

### v1.0.1 Path Resolution

**Diagnostic Commands:**
```bash
# Test with absolute paths
uv run python src/repo_distiller.py   /absolute/path/to/source   /absolute/path/to/dest   --dry-run -v

# Test with relative paths (now works!)
uv run python src/repo_distiller.py   ../source-project   ./dest-project   --dry-run -v
```

**If you still see path errors:**
1. Check that source directory exists: `ls -la ../source-project`
2. Check permissions: `ls -ld ../source-project`
3. Verify you're running v1.0.1: `uv run python src/repo_distiller.py --version`

---

**Document Version**: 1.0.1  
**Last Updated**: 2025-12-14  
**Optimized for**: AI-assisted coding with uv + path resolution fix
