#!/usr/bin/env python3
"""
Repository Distiller - Intelligent repository filtering for LLM context preparation.

This utility creates a filtered copy of a source repository, optimized for providing
context to Large Language Models in AI-assisted coding workflows.

Usage:
    python src/repo_distiller.py <source_dir> <destination_dir> [options]
    uv run python src/repo_distiller.py <source_dir> <destination_dir> [options]

Version: 1.1.1 (Priority Cascade + filename veto enhancements)
License: MIT
"""

import argparse
import csv
import json
import logging
import re
import shutil
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: uv add pyyaml", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# CONFIGURATION & DATA STRUCTURES
# ============================================================================

class FilterAction(Enum):
    """Enumeration of possible actions for a file."""
    COPY = "COPY"
    SAMPLE = "SAMPLE"
    SKIP = "SKIP"


@dataclass
class FilterStats:
    """Statistics tracking for the distillation process."""
    scanned: int = 0
    copied: int = 0
    sampled: int = 0
    skipped: int = 0
    errors: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)

    def add_skip_reason(self, reason: str) -> None:
        """Track skip reasons for summary reporting."""
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


@dataclass
class DistillerConfig:
    """Configuration container for the distiller."""
    max_file_size_mb: float
    whitelist_files: List[str]
    whitelist_directories: List[str]
    blacklist_files: List[str]
    blacklist_extensions: List[str]
    blacklist_patterns: List[re.Pattern]
    blacklist_directories: List[str]
    blacklist_filename_substrings: List[str]
    blacklist_datetime_stamp_yyyymmdd: bool
    data_sampling_enabled: bool
    data_sampling_extensions: Set[str]
    data_sampling_include_header: bool
    data_sampling_head_rows: int
    data_sampling_tail_rows: int
    ai_coding_env: str = 'chat'

    
@staticmethod
def from_yaml(config_path: Path) -> 'DistillerConfig':
    """Load and parse configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")

    blacklist_cfg = config_data.get('blacklist', {}) or {}
    whitelist_cfg = config_data.get('whitelist', {}) or {}
    sampling_cfg = config_data.get('data_sampling', {}) or {}

    # Parse and compile regex patterns (filename-only)
    patterns: List[re.Pattern] = []
    for pattern_str in blacklist_cfg.get('patterns', []) or []:
        try:
            patterns.append(re.compile(pattern_str))
        except re.error as e:
            logging.warning(f"Invalid regex pattern '{pattern_str}': {e}")

    # Filename substring blacklist (case-insensitive contains checks)
    filename_substrings = blacklist_cfg.get('filename_substrings', []) or []
    if not isinstance(filename_substrings, list):
        filename_substrings = []

    # Datetime-stamp blacklist flag (YYYYMMDD in filename)
    datetime_stamp_yyyymmdd = blacklist_cfg.get('datetime_stamp_yyyymmdd', True)
    if not isinstance(datetime_stamp_yyyymmdd, bool):
        datetime_stamp_yyyymmdd = True

    # Normalize extensions (ensure leading dot)
    extensions = blacklist_cfg.get('extensions', []) or []
    normalized_exts = [ext if str(ext).startswith('.') else f'.{ext}' for ext in extensions]

    # Parse data sampling config
    sampling_exts = sampling_cfg.get('target_extensions', []) or []
    normalized_sampling_exts = {ext if str(ext).startswith('.') else f'.{ext}' for ext in sampling_exts}

    return DistillerConfig(
        max_file_size_mb=float(config_data.get('max_file_size_mb', 5.0)),
        whitelist_files=whitelist_cfg.get('files', []) or [],
        whitelist_directories=whitelist_cfg.get('directories', []) or [],
        blacklist_files=blacklist_cfg.get('files', []) or [],
        blacklist_extensions=normalized_exts,
        blacklist_patterns=patterns,
        blacklist_directories=blacklist_cfg.get('directories', []) or [],
        blacklist_filename_substrings=filename_substrings,
        blacklist_datetime_stamp_yyyymmdd=datetime_stamp_yyyymmdd,
        data_sampling_enabled=bool(sampling_cfg.get('enabled', True)),
        data_sampling_extensions=normalized_sampling_exts,
        data_sampling_include_header=bool(sampling_cfg.get('include_header', True)),
        data_sampling_head_rows=int(sampling_cfg.get('head_rows', 5)),
        data_sampling_tail_rows=int(sampling_cfg.get('tail_rows', 5)),
        ai_coding_env=str(config_data.get('ai_coding_env', 'chat'))
    )


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure logging with both console and file handlers."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"log_{timestamp}.txt"

    logger = logging.getLogger('repo_distiller')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler - concise format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(levelname)-8s | %(message)s'))

    # File handler - detailed format
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-24s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


# ============================================================================
# CORE FILTERING LOGIC
# ============================================================================

class RepositoryDistiller:
    """Main class for repository distillation operations."""

    def __init__(self, config: DistillerConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.stats = FilterStats()

    # -------------------------
    # Path / pattern utilities
    # -------------------------

    @staticmethod
    def _to_rel_posix(path: Path, base_path: Path) -> Optional[str]:
        """Return a POSIX-style relative path string, or None if not relative."""
        path = path.resolve()
        base_path = base_path.resolve()
        try:
            rel = path.relative_to(base_path)
        except ValueError:
            return None
        return rel.as_posix()

    @staticmethod
    def _normalize_pattern(pattern: str) -> str:
        """Normalize config patterns to forward-slash, no leading ./"""
        p = (pattern or "").strip().replace('\\', '/')
        while p.startswith('./'):
            p = p[2:]
        return p

    @staticmethod
    def _has_wildcards(pattern: str) -> bool:
        return any(ch in pattern for ch in ['*', '?', '['])

    def _match_file_patterns(self, rel_posix: str, patterns: List[str]) -> bool:
        """Match file patterns (exact or glob) against a relative posix path."""
        rel_path = PurePosixPath(rel_posix)
        for raw in patterns:
            pat = self._normalize_pattern(raw)
            pat = pat.rstrip('/')  # file patterns should not rely on trailing slash
            if not pat:
                continue

            # Exact match
            if not self._has_wildcards(pat) and rel_posix == pat:
                return True

            # Glob match
            if self._has_wildcards(pat):
                try:
                    if rel_path.match(pat):
                        return True
                except Exception as e:
                    self.logger.warning(f"Invalid glob pattern '{raw}': {e}")
        return False

    def _match_dir_patterns(self, rel_posix: str, patterns: List[str]) -> bool:
        """Match directory patterns by prefix semantics and optional glob."""
        rel_path = PurePosixPath(rel_posix)
        for raw in patterns:
            pat = self._normalize_pattern(raw)
            if not pat:
                continue

            pat = pat.rstrip('/')

            # Non-glob directory pattern: prefix match
            if not self._has_wildcards(pat):
                if rel_posix == pat or rel_posix.startswith(pat + '/'):
                    return True
                continue

            # Glob directory pattern:
            # - direct match (covers patterns like "src/**")
            # - prefix match by appending "/**"
            try:
                if rel_path.match(pat) or rel_path.match(pat + '/**'):
                    return True
            except Exception as e:
                self.logger.warning(f"Invalid glob pattern '{raw}': {e}")
        return False

    # -------------------------
    # Sampling decision helpers
    # -------------------------

    def _filename_contains_yyyymmdd_stamp(self, filename: str) -> Optional[str]:
        """Return the matched YYYYMMDD substring if present and valid, else None."""
        if not self.config.blacklist_datetime_stamp_yyyymmdd:
            return None

        for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", filename):
            candidate = m.group(1)
            try:
                datetime.strptime(candidate, "%Y%m%d")
                return candidate
            except Exception:
                continue
        return None

    def _filename_contains_blacklisted_substring(self, filename: str) -> Optional[str]:
        """Return the configured substring that matched (case-insensitive), else None."""
        substrings = self.config.blacklist_filename_substrings or []
        if not substrings:
            return None

        haystack = filename.upper()
        for raw in substrings:
            if not isinstance(raw, str):
                continue
            needle = raw.strip().upper()
            if not needle:
                continue
            if needle in haystack:
                return raw
        return None

    def _should_sample_data_file(self, path: Path) -> bool:
        if not self.config.data_sampling_enabled:
            return False
        if not path.is_file():
            return False
        return path.suffix.lower() in self.config.data_sampling_extensions

    # -------------------------
    # Priority Cascade decision

        # -------------------------

    def determine_action(self, path: Path, base_path: Path) -> Tuple[FilterAction, Optional[str]]:
        """
        Determine action using a Tiered Priority Cascade:

          Tier 1 (Golden Ticket): whitelist.files
            - Force include (COPY/SAMPLE), bypassing size and Tier 4 general exclusions.

          Tier 2 (Explicit Veto): blacklist.files, blacklist.patterns
            - Force exclude.

          Tier 3 (Scope): whitelist.directories
            - Must be inside at least one whitelisted directory to proceed.

          Tier 4 (Sanity): blacklist.directories, blacklist.extensions, max_file_size_mb
            - General exclusions applied only after Tier 3 passes.
        """
        path = path.resolve()
        base_path = base_path.resolve()

        rel_posix = self._to_rel_posix(path, base_path)
        if rel_posix is None:
            return FilterAction.SKIP, "outside_repository_root"

        # --- Tier 1: Golden Ticket (explicit file whitelist) ---
        if self._match_file_patterns(rel_posix, self.config.whitelist_files):
            if self._should_sample_data_file(path):
                return FilterAction.SAMPLE, "tier1_whitelist_file_sampled"
            return FilterAction.COPY, "tier1_whitelist_file"

        # --- Tier 2: Explicit Veto (explicit file blacklist + filename regex patterns) ---
        if self._match_file_patterns(rel_posix, self.config.blacklist_files):
            return FilterAction.SKIP, "tier2_blacklist_file"

        filename = path.name
        # Tier 2b: Datetime-stamp veto (YYYYMMDD)
        stamp = self._filename_contains_yyyymmdd_stamp(filename)
        if stamp:
            return FilterAction.SKIP, f"tier2_blacklist_datetime_stamp:{stamp}"

        # Tier 2c: Substring vetoes (case-insensitive)
        sub = self._filename_contains_blacklisted_substring(filename)
        if sub:
            return FilterAction.SKIP, f"tier2_blacklist_filename_substring:{sub}"

        for pattern in self.config.blacklist_patterns:
            try:
                if pattern.search(filename):
                    return FilterAction.SKIP, f"tier2_blacklist_pattern:{pattern.pattern}"
            except Exception as e:
                self.logger.warning(f"Regex evaluation failed for '{pattern.pattern}': {e}")

        # --- Tier 3: Scope check (whitelist-only mode for directories) ---
        if not self._match_dir_patterns(rel_posix, self.config.whitelist_directories):
            return FilterAction.SKIP, "tier3_not_in_whitelist_scope"

        # --- Tier 4: Sanity checks (general exclusions) ---
        if self._match_dir_patterns(rel_posix, self.config.blacklist_directories):
            return FilterAction.SKIP, "tier4_blacklist_directory"

        if path.suffix.lower() in self.config.blacklist_extensions:
            return FilterAction.SKIP, f"tier4_blacklist_ext:{path.suffix.lower()}"

        if path.is_file():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                return FilterAction.SKIP, f"tier4_file_size>{self.config.max_file_size_mb}MB"

        # Final: sample vs copy (within allowed scope)
        if self._should_sample_data_file(path):
            return FilterAction.SAMPLE, "tier4_sampled"
        return FilterAction.COPY, "tier4_copied"

    # =========================================================================
    # Sampling implementations
    # =========================================================================

    def _sample_delimited_file(self, source: Path, destination: Path, delimiter: str) -> bool:
        """
        Stream-sample a delimited text file (CSV/TSV) by writing:
          [header?] + first N rows + separator row + last M rows

        This avoids loading the entire file into memory.
        """
        try:
            source = source.resolve()
            destination = destination.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)

            include_header = self.config.data_sampling_include_header
            head_n = max(0, int(self.config.data_sampling_head_rows))
            tail_n = max(0, int(self.config.data_sampling_tail_rows))

            header: Optional[List[str]] = None
            head_rows: List[List[str]] = []
            tail_rows: deque = deque(maxlen=tail_n)
            total_data_rows = 0
            num_cols = 1

            with open(source, 'r', encoding='utf-8', newline='', errors='replace') as src:
                reader = csv.reader(src, delimiter=delimiter)

                for row_idx, row in enumerate(reader):
                    # Track columns for nicer separator formatting
                    if row and len(row) > num_cols:
                        num_cols = len(row)

                    if row_idx == 0 and include_header:
                        header = row
                        continue

                    total_data_rows += 1
                    if len(head_rows) < head_n:
                        head_rows.append(row)
                    tail_rows.append(row)

            # Empty file: copy intact
            if header is None and total_data_rows == 0:
                self.logger.warning(f"Empty delimited file: {source}")
                shutil.copy2(source, destination)
                return True

            # Small enough: copy intact
            if total_data_rows <= (head_n + tail_n):
                shutil.copy2(source, destination)
                self.logger.info(f"SAMPLED[DELIM - copied intact]: {source.name} ({total_data_rows} data rows)")
                return True

            omitted = total_data_rows - len(head_rows) - len(tail_rows)

            with open(destination, 'w', encoding='utf-8', newline='') as dst:
                writer = csv.writer(dst, delimiter=delimiter)

                if header is not None:
                    writer.writerow(header)
                    if len(header) > num_cols:
                        num_cols = len(header)

                for r in head_rows:
                    writer.writerow(r)

                note = f"... ({omitted} rows omitted) ..."
                sep_row = [note] + ([''] * max(0, num_cols - 1))
                writer.writerow(sep_row)

                for r in list(tail_rows):
                    writer.writerow(r)

            self.logger.info(f"SAMPLED[DELIM]: {source.name} ({total_data_rows} data rows)")
            return True

        except Exception as e:
            self.logger.error(f"Error sampling delimited file {source.name}: {e}")
            return False

    def _sample_json_file(self, source: Path, destination: Path) -> bool:
        """Sample a JSON/JSONL file by copying head + tail objects."""
        try:
            source = source.resolve()
            destination = destination.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)

            # JSONL: stream lines
            if source.suffix.lower() == '.jsonl':
                head: List[str] = []
                tail: deque = deque(maxlen=max(0, int(self.config.data_sampling_tail_rows)))
                total_objects = 0

                with open(source, 'r', encoding='utf-8', errors='replace') as src:
                    for raw_line in src:
                        line = raw_line.rstrip('\n\r')
                        if not line.strip():
                            continue
                        total_objects += 1
                        if len(head) < self.config.data_sampling_head_rows:
                            head.append(line)
                        tail.append(line)

                if total_objects == 0:
                    self.logger.warning(f"Empty JSONL file: {source}")
                    shutil.copy2(source, destination)
                    return True

                if total_objects <= (self.config.data_sampling_head_rows + self.config.data_sampling_tail_rows):
                    shutil.copy2(source, destination)
                    self.logger.info(f"SAMPLED[JSONL - copied intact]: {source.name} ({total_objects} objects)")
                    return True

                omitted = total_objects - len(head) - len(tail)
                with open(destination, 'w', encoding='utf-8') as dst:
                    if head:
                        dst.write('\n'.join(head))
                        dst.write('\n\n')
                    dst.write(f"... ({omitted} objects omitted) ...\n\n")
                    dst.write('\n'.join(list(tail)))

                self.logger.info(f"SAMPLED[JSONL]: {source.name} ({total_objects} objects)")
                return True

            # Regular JSON: load and sample arrays only
            with open(source, 'r', encoding='utf-8', errors='replace') as src:
                content = src.read().strip()

            try:
                data = json.loads(content) if content else None
            except json.JSONDecodeError as e:
                self.logger.warning(f"Invalid JSON in {source.name}: {e}. Copying as-is.")
                shutil.copy2(source, destination)
                return True

            if isinstance(data, list):
                total_items = len(data)
                head_limit = max(0, int(self.config.data_sampling_head_rows))
                tail_limit = max(0, int(self.config.data_sampling_tail_rows))

                if total_items <= (head_limit + tail_limit):
                    shutil.copy2(source, destination)
                    self.logger.info(f"SAMPLED[JSON - copied intact]: {source.name} ({total_items} items)")
                    return True

                head = data[:head_limit]
                tail = data[-tail_limit:] if tail_limit > 0 else []

                sampled = {
                    "_sampled": True,
                    "_total_items": total_items,
                    "_omitted_items": total_items - len(head) - len(tail),
                    "head": head,
                    "tail": tail,
                }

                with open(destination, 'w', encoding='utf-8') as dst:
                    json.dump(sampled, dst, indent=2, ensure_ascii=False)

                self.logger.info(f"SAMPLED[JSON]: {source.name} ({total_items} items)")
                return True

            # Objects/primitives: copy as-is
            shutil.copy2(source, destination)
            self.logger.debug(f"JSON object/primitive (not sampled): {source.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error sampling JSON {source.name}: {e}")
            return False

    # =========================================================================
    # File processing & distillation
    # =========================================================================

    def process_file(self, source: Path, destination: Path, action: FilterAction) -> bool:
        """Process a single file according to the determined action."""
        try:
            source = source.resolve()
            destination = destination.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)

            if action == FilterAction.COPY:
                shutil.copy2(source, destination)
                self.logger.debug(f"COPIED: {source}")
                self.stats.copied += 1
                return True

            if action == FilterAction.SAMPLE:
                ext = source.suffix.lower()
                if ext == '.csv':
                    ok = self._sample_delimited_file(source, destination, delimiter=',')
                elif ext == '.tsv':
                    ok = self._sample_delimited_file(source, destination, delimiter='\t')
                elif ext in {'.json', '.jsonl'}:
                    ok = self._sample_json_file(source, destination)
                else:
                    self.logger.warning(f"Unknown sampling type '{ext}' for {source}. Copying as-is.")
                    shutil.copy2(source, destination)
                    ok = True

                if ok:
                    self.stats.sampled += 1
                else:
                    self.stats.errors += 1
                return ok

            # SKIP should be handled by caller loop
            self.stats.skipped += 1
            return True

        except Exception as e:
            self.logger.error(f"Error processing {source}: {e}")
            self.stats.errors += 1
            return False

    def distill(self, source_dir: Path, dest_dir: Path, dry_run: bool = False) -> bool:
        """Main distillation process: walk source directory and filter to destination."""
        # Resolve all paths to absolute paths (prevents relative_to() mismatch errors)
        source_dir = source_dir.resolve()
        dest_dir = dest_dir.resolve()

        self.logger.info(f"{'[DRY RUN] ' if dry_run else ''}Starting distillation...")
        self.logger.info(f"Source: {source_dir}")
        self.logger.info(f"Destination: {dest_dir}")
        self.logger.info(f"Configuration: AI Coding Env = {self.config.ai_coding_env}")

        if not source_dir.exists():
            self.logger.error(f"Source directory does not exist: {source_dir}")
            return False
        if not source_dir.is_dir():
            self.logger.error(f"Source path is not a directory: {source_dir}")
            return False

        # Prepare destination directory
        if not dry_run:
            if dest_dir.exists():
                if not self._confirm_overwrite(dest_dir):
                    self.logger.info("Operation cancelled by user.")
                    return False
                shutil.rmtree(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)

        # Walk the source directory (files only)
        try:
            for path in source_dir.rglob('*'):
                if not path.is_file():
                    continue

                self.stats.scanned += 1
                path = path.resolve()

                rel_posix = self._to_rel_posix(path, source_dir)
                if rel_posix is None:
                    self.stats.skipped += 1
                    self.stats.add_skip_reason("outside_repository_root")
                    continue

                action, reason = self.determine_action(path, source_dir)

                if action == FilterAction.SKIP:
                    self.stats.skipped += 1
                    self.stats.add_skip_reason(reason or "skip")
                    self.logger.debug(f"SKIP[{reason}]: {rel_posix}")
                    continue

                dest_path = dest_dir / Path(rel_posix)

                if dry_run:
                    self.logger.info(f"[DRY RUN] {action.value}: {rel_posix}")
                    if action == FilterAction.COPY:
                        self.stats.copied += 1
                    elif action == FilterAction.SAMPLE:
                        self.stats.sampled += 1
                else:
                    self.process_file(path, dest_path, action)

        except Exception as e:
            self.logger.error(f"Fatal error during distillation: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

        self._print_summary()
        return self.stats.errors == 0

    def _confirm_overwrite(self, dest_dir: Path) -> bool:
        """Prompt user to confirm overwriting existing destination."""
        print(f"\nWARNING: Destination directory exists: {dest_dir}")
        print("All contents will be deleted. Continue? (yes/no): ", end='')
        try:
            response = input().strip().lower()
            return response in {'yes', 'y'}
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    def _print_summary(self) -> None:
        """Print a summary report of the distillation process."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("DISTILLATION SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Total files scanned:  {self.stats.scanned}")
        self.logger.info(f"Files copied:         {self.stats.copied}")
        self.logger.info(f"Files sampled:        {self.stats.sampled}")
        self.logger.info(f"Files skipped:        {self.stats.skipped}")
        self.logger.info(f"Errors:               {self.stats.errors}")

        if self.stats.skipped_reasons:
            self.logger.info("\nSkip reasons breakdown:")
            for reason, count in sorted(self.stats.skipped_reasons.items(), key=lambda x: -x[1]):
                self.logger.info(f"  {reason:34s}: {count:>6d}")
        self.logger.info("=" * 70 + "\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Repository Distiller - Intelligent filtering for LLM context preparation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/repo_distiller.py ./my-repo ./distilled-repo
  uv run python src/repo_distiller.py ./my-repo ./distilled-repo
  python src/repo_distiller.py ./my-repo ./distilled-repo --dry-run
  python src/repo_distiller.py ./my-repo ./distilled-repo -c custom_config.yaml -v

For more information, see docs/user-manual.md
        """
    )

    parser.add_argument('source_dir', type=Path, help='Source repository directory to distill')
    parser.add_argument('destination_dir', type=Path, help='Destination directory for distilled output')
    parser.add_argument('-c', '--config', type=Path, default=Path('./config.yaml'),
                        help='Path to YAML configuration file (default: ./config.yaml)')
    parser.add_argument('-d', '--dry-run', action='store_true', help='Preview actions without copying')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging (DEBUG)')
    parser.add_argument('--log-dir', type=Path, default=Path('./logs'),
                        help='Directory for log files (default: ./logs)')
    parser.add_argument('--version', action='version', version='Repository Distiller v1.1.1')

    args = parser.parse_args()

    # Resolve all paths to absolute paths
    args.source_dir = args.source_dir.resolve()
    args.destination_dir = args.destination_dir.resolve()
    args.config = args.config.resolve()
    args.log_dir = args.log_dir.resolve()

    # Validate source directory exists (even for dry-run)
    if not args.source_dir.exists():
        parser.error(f"Source directory does not exist: {args.source_dir}")

    return args


def main() -> int:
    args = parse_arguments()
    logger = setup_logging(args.log_dir, verbose=args.verbose)

    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = DistillerConfig.from_yaml(args.config)
        logger.info(f"Configuration loaded successfully (AI Coding Env: {config.ai_coding_env})")

        distiller = RepositoryDistiller(config, logger)

        success = distiller.distill(
            source_dir=args.source_dir,
            dest_dir=args.destination_dir,
            dry_run=args.dry_run
        )

        if success:
            logger.info("✓ Distillation completed successfully")
            return 0

        logger.error("✗ Distillation completed with errors")
        return 1

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
