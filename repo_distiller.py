#!/usr/bin/env python3
"""
Repository Distiller - Intelligent repository filtering for LLM context preparation.

This utility creates a filtered copy of a source repository, optimized for providing
context to Large Language Models in AI-assisted coding workflows.

Usage:
    python repo_distiller.py <source_dir> <destination_dir> [options]

Author: Generated via AI-assisted spec-driven development
Version: 1.0.0
License: MIT
"""

import argparse
import logging
import sys
import shutil
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
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

    def add_skip_reason(self, reason: str):
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
                config_data = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")

        # Parse and compile regex patterns
        patterns = []
        for pattern_str in config_data.get('blacklist', {}).get('patterns', []):
            try:
                patterns.append(re.compile(pattern_str))
            except re.error as e:
                logging.warning(f"Invalid regex pattern '{pattern_str}': {e}")

        # Normalize extensions (ensure leading dot)
        extensions = config_data.get('blacklist', {}).get('extensions', [])
        normalized_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]

        # Parse data sampling config
        data_sampling = config_data.get('data_sampling', {})
        sampling_exts = data_sampling.get('target_extensions', [])
        normalized_sampling_exts = {ext if ext.startswith('.') else f'.{ext}' for ext in sampling_exts}

        return DistillerConfig(
            max_file_size_mb=config_data.get('max_file_size_mb', 5.0),
            whitelist_files=config_data.get('whitelist', {}).get('files', []),
            whitelist_directories=config_data.get('whitelist', {}).get('directories', []),
            blacklist_files=config_data.get('blacklist', {}).get('files', []),
            blacklist_extensions=normalized_exts,
            blacklist_patterns=patterns,
            blacklist_directories=config_data.get('blacklist', {}).get('directories', []),
            data_sampling_enabled=data_sampling.get('enabled', True),
            data_sampling_extensions=normalized_sampling_exts,
            data_sampling_include_header=data_sampling.get('include_header', True),
            data_sampling_head_rows=data_sampling.get('head_rows', 5),
            data_sampling_tail_rows=data_sampling.get('tail_rows', 5),
            ai_coding_env=config_data.get('ai_coding_env', 'chat')
        )


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """
    Configure logging with both console and file handlers.

    Args:
        log_dir: Directory for log files
        verbose: If True, set log level to DEBUG

    Returns:
        Configured logger instance
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"log_{timestamp}.txt"

    logger = logging.getLogger('repo_distiller')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler - concise format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_format = logging.Formatter(
        '%(levelname)-8s | %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler - detailed format
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)

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

    def _matches_glob_pattern(self, path: Path, patterns: List[str], base_path: Path) -> bool:
        """
        Check if a path matches any glob pattern in the list.

        Args:
            path: Path to check
            patterns: List of glob patterns
            base_path: Base repository path for relative matching

        Returns:
            True if path matches any pattern
        """
        rel_path = path.relative_to(base_path)
        rel_path_str = str(rel_path)

        for pattern in patterns:
            # Normalize pattern for consistent matching
            pattern_normalized = pattern.strip('./').rstrip('/')

            # Direct match
            if rel_path_str == pattern_normalized:
                return True

            # Directory prefix match (for directory patterns)
            if path.is_dir() and rel_path_str.startswith(pattern_normalized):
                return True

            # Check if file is within a directory pattern
            if '/' in pattern_normalized:
                pattern_parts = Path(pattern_normalized).parts
                rel_parts = rel_path.parts
                if len(rel_parts) >= len(pattern_parts):
                    if rel_parts[:len(pattern_parts)] == pattern_parts:
                        return True

            # Glob pattern matching (supports *)
            if '*' in pattern:
                try:
                    # Use pathlib's match for glob patterns
                    if rel_path.match(pattern_normalized):
                        return True
                except Exception as e:
                    self.logger.warning(f"Invalid glob pattern '{pattern}': {e}")

        return False

    def _is_whitelisted(self, path: Path, base_path: Path) -> bool:
        """Check if path is whitelisted (highest priority)."""
        # File whitelist
        if self._matches_glob_pattern(path, self.config.whitelist_files, base_path):
            self.logger.debug(f"WHITELIST[file]: {path.relative_to(base_path)}")
            return True

        # Directory whitelist
        if self._matches_glob_pattern(path, self.config.whitelist_directories, base_path):
            self.logger.debug(f"WHITELIST[dir]: {path.relative_to(base_path)}")
            return True

        return False

    def _is_blacklisted(self, path: Path, base_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if path is blacklisted and return the reason.

        Returns:
            Tuple of (is_blacklisted, reason)
        """
        # File size check (applied after whitelist per requirements)
        if path.is_file():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                return True, f"file_size>{self.config.max_file_size_mb}MB"

        # Specific file blacklist
        if self._matches_glob_pattern(path, self.config.blacklist_files, base_path):
            return True, "blacklist_file"

        # Directory blacklist
        if self._matches_glob_pattern(path, self.config.blacklist_directories, base_path):
            return True, "blacklist_directory"

        # Extension blacklist
        if path.suffix.lower() in self.config.blacklist_extensions:
            return True, f"blacklist_ext:{path.suffix}"

        # Regex pattern blacklist
        filename = path.name
        for pattern in self.config.blacklist_patterns:
            if pattern.search(filename):
                return True, f"blacklist_pattern:{pattern.pattern}"

        return False, None

    def _should_sample_data_file(self, path: Path) -> bool:
        """Determine if file should be sampled instead of copied verbatim."""
        if not self.config.data_sampling_enabled:
            return False

        if not path.is_file():
            return False

        return path.suffix.lower() in self.config.data_sampling_extensions

    def determine_action(self, path: Path, base_path: Path) -> Tuple[FilterAction, Optional[str]]:
        """
        Determine what action to take for a given path.

        Args:
            path: Path to evaluate
            base_path: Repository base path

        Returns:
            Tuple of (action, skip_reason)
        """
        # Step 1: Whitelist check (highest priority)
        if self._is_whitelisted(path, base_path):
            # Whitelisted files can still be sampled if they match criteria
            if self._should_sample_data_file(path):
                return FilterAction.SAMPLE, None
            return FilterAction.COPY, None

        # Step 2: Blacklist check
        is_blacklisted, reason = self._is_blacklisted(path, base_path)
        if is_blacklisted:
            return FilterAction.SKIP, reason

        # Step 3: Data sampling check
        if self._should_sample_data_file(path):
            return FilterAction.SAMPLE, None

        # Step 4: Default action
        return FilterAction.COPY, None

    def _sample_csv_file(self, source: Path, destination: Path) -> bool:
        """
        Sample a CSV file by copying header + head rows + tail rows.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(source, 'r', encoding='utf-8', newline='', errors='replace') as src:
                reader = csv.reader(src)

                # Read all rows into memory (for tail access)
                all_rows = list(reader)

                if len(all_rows) == 0:
                    self.logger.warning(f"Empty CSV file: {source}")
                    shutil.copy2(source, destination)
                    return True

                # Determine header
                has_header = self.config.data_sampling_include_header
                header_rows = [all_rows[0]] if has_header and len(all_rows) > 0 else []
                data_start_idx = 1 if has_header else 0

                # Calculate head and tail
                data_rows = all_rows[data_start_idx:]
                total_data_rows = len(data_rows)

                if total_data_rows <= (self.config.data_sampling_head_rows + self.config.data_sampling_tail_rows):
                    # File is small enough, copy all
                    with open(destination, 'w', encoding='utf-8', newline='') as dst:
                        writer = csv.writer(dst)
                        writer.writerows(all_rows)
                else:
                    # Sample head and tail
                    head = data_rows[:self.config.data_sampling_head_rows]
                    tail = data_rows[-self.config.data_sampling_tail_rows:]

                    with open(destination, 'w', encoding='utf-8', newline='') as dst:
                        writer = csv.writer(dst)

                        # Write header
                        if header_rows:
                            writer.writerows(header_rows)

                        # Write head
                        writer.writerows(head)

                        # Write separator comment
                        separator = [f"... ({total_data_rows - len(head) - len(tail)} rows omitted) ..."]
                        writer.writerow(separator)

                        # Write tail
                        writer.writerows(tail)

                self.logger.info(f"SAMPLED[CSV]: {source.relative_to(Path.cwd())} ({len(all_rows)} rows)")
                return True

        except Exception as e:
            self.logger.error(f"Error sampling CSV {source}: {e}")
            return False

    def _sample_json_file(self, source: Path, destination: Path) -> bool:
        """
        Sample a JSON/JSONL file by copying head + tail objects.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(source, 'r', encoding='utf-8', errors='replace') as src:
                content = src.read().strip()

                # Handle JSONL (newline-delimited JSON)
                if source.suffix.lower() == '.jsonl':
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    total_objects = len(lines)

                    if total_objects <= (self.config.data_sampling_head_rows + self.config.data_sampling_tail_rows):
                        # Small file, copy all
                        shutil.copy2(source, destination)
                    else:
                        head = lines[:self.config.data_sampling_head_rows]
                        tail = lines[-self.config.data_sampling_tail_rows:]

                        with open(destination, 'w', encoding='utf-8') as dst:
                            dst.write('\n'.join(head))
                            dst.write(f'\n\n... ({total_objects - len(head) - len(tail)} objects omitted) ...\n\n')
                            dst.write('\n'.join(tail))

                    self.logger.info(f"SAMPLED[JSONL]: {source.relative_to(Path.cwd())} ({total_objects} objects)")
                    return True

                # Handle regular JSON (array or object)
                else:
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON in {source}: {e}. Copying as-is.")
                        shutil.copy2(source, destination)
                        return True

                    # If JSON is an array, sample it
                    if isinstance(data, list):
                        total_items = len(data)

                        if total_items <= (self.config.data_sampling_head_rows + self.config.data_sampling_tail_rows):
                            shutil.copy2(source, destination)
                        else:
                            head = data[:self.config.data_sampling_head_rows]
                            tail = data[-self.config.data_sampling_tail_rows:]

                            sampled = {
                                "_sampled": True,
                                "_total_items": total_items,
                                "_omitted_items": total_items - len(head) - len(tail),
                                "head": head,
                                "tail": tail
                            }

                            with open(destination, 'w', encoding='utf-8') as dst:
                                json.dump(sampled, dst, indent=2, ensure_ascii=False)

                        self.logger.info(f"SAMPLED[JSON]: {source.relative_to(Path.cwd())} ({total_items} items)")
                    else:
                        # JSON is an object or primitive, copy as-is
                        shutil.copy2(source, destination)
                        self.logger.debug(f"JSON object/primitive (not sampled): {source.relative_to(Path.cwd())}")

                    return True

        except Exception as e:
            self.logger.error(f"Error sampling JSON {source}: {e}")
            return False

    def process_file(self, source: Path, destination: Path, action: FilterAction) -> bool:
        """
        Process a single file according to the determined action.

        Args:
            source: Source file path
            destination: Destination file path
            action: Action to perform

        Returns:
            True if successful, False otherwise
        """
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)

            if action == FilterAction.COPY:
                shutil.copy2(source, destination)
                self.logger.debug(f"COPIED: {source.relative_to(Path.cwd())}")
                self.stats.copied += 1
                return True

            elif action == FilterAction.SAMPLE:
                # Determine file type and sample accordingly
                ext = source.suffix.lower()

                if ext == '.csv' or ext == '.tsv':
                    success = self._sample_csv_file(source, destination)
                elif ext in {'.json', '.jsonl'}:
                    success = self._sample_json_file(source, destination)
                else:
                    self.logger.warning(f"Unknown data file type for sampling: {ext}. Copying as-is.")
                    shutil.copy2(source, destination)
                    success = True

                if success:
                    self.stats.sampled += 1
                else:
                    self.stats.errors += 1
                return success

            else:  # SKIP
                self.logger.debug(f"SKIPPED: {source.relative_to(Path.cwd())}")
                self.stats.skipped += 1
                return True

        except Exception as e:
            self.logger.error(f"Error processing {source}: {e}")
            self.stats.errors += 1
            return False

    def distill(self, source_dir: Path, dest_dir: Path, dry_run: bool = False) -> bool:
        """
        Main distillation process: walk source directory and filter to destination.

        Args:
            source_dir: Source repository directory
            dest_dir: Destination directory
            dry_run: If True, only simulate actions without copying

        Returns:
            True if successful, False if errors occurred
        """
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

        # Walk the source directory
        try:
            for path in source_dir.rglob('*'):
                self.stats.scanned += 1

                # Only process files (directories are created as needed)
                if not path.is_file():
                    continue

                # Determine action
                action, skip_reason = self.determine_action(path, source_dir)

                # Log and track
                if action == FilterAction.SKIP:
                    if skip_reason:
                        self.stats.add_skip_reason(skip_reason)
                    self.logger.debug(f"SKIP[{skip_reason}]: {path.relative_to(source_dir)}")
                    self.stats.skipped += 1
                    continue

                # Construct destination path
                rel_path = path.relative_to(source_dir)
                dest_path = dest_dir / rel_path

                # Execute action
                if dry_run:
                    self.logger.info(f"[DRY RUN] {action.value}: {rel_path}")
                    if action == FilterAction.COPY:
                        self.stats.copied += 1
                    elif action == FilterAction.SAMPLE:
                        self.stats.sampled += 1
                else:
                    self.process_file(path, dest_path, action)

        except Exception as e:
            self.logger.error(f"Fatal error during distillation: {e}")
            return False

        # Print summary
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

    def _print_summary(self):
        """Print a summary report of the distillation process."""
        self.logger.info("\n" + "="*70)
        self.logger.info("DISTILLATION SUMMARY")
        self.logger.info("="*70)
        self.logger.info(f"Total files scanned:  {self.stats.scanned}")
        self.logger.info(f"Files copied:         {self.stats.copied}")
        self.logger.info(f"Files sampled:        {self.stats.sampled}")
        self.logger.info(f"Files skipped:        {self.stats.skipped}")
        self.logger.info(f"Errors:               {self.stats.errors}")

        if self.stats.skipped_reasons:
            self.logger.info("\nSkip reasons breakdown:")
            for reason, count in sorted(self.stats.skipped_reasons.items(), key=lambda x: -x[1]):
                self.logger.info(f"  {reason:30s}: {count:>6d}")

        self.logger.info("="*70 + "\n")


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
  # Basic usage
  python repo_distiller.py ./my-repo ./distilled-repo

  # Dry run to preview actions
  python repo_distiller.py ./my-repo ./distilled-repo --dry-run

  # Verbose logging with custom config
  python repo_distiller.py ./my-repo ./distilled-repo -c custom_config.yaml -v

For more information, see docs/user-manual.md
        """
    )

    parser.add_argument(
        'source_dir',
        type=Path,
        help='Source repository directory to distill'
    )

    parser.add_argument(
        'destination_dir',
        type=Path,
        help='Destination directory for distilled output'
    )

    parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('./config.yaml'),
        help='Path to YAML configuration file (default: ./config.yaml)'
    )

    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Preview actions without actually copying files'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    parser.add_argument(
        '--log-dir',
        type=Path,
        default=Path('./logs'),
        help='Directory for log files (default: ./logs)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Repository Distiller v1.0.0'
    )

    args = parser.parse_args()

    # Validate source directory exists
    if not args.dry_run and not args.source_dir.exists():
        parser.error(f"Source directory does not exist: {args.source_dir}")

    return args


def main() -> int:
    """Main entry point for the repository distiller."""
    args = parse_arguments()

    # Setup logging
    logger = setup_logging(args.log_dir, verbose=args.verbose)

    try:
        # Load configuration
        logger.info(f"Loading configuration from: {args.config}")
        config = DistillerConfig.from_yaml(args.config)
        logger.info(f"Configuration loaded successfully (AI Coding Env: {config.ai_coding_env})")

        # Create distiller instance
        distiller = RepositoryDistiller(config, logger)

        # Execute distillation
        success = distiller.distill(
            source_dir=args.source_dir,
            dest_dir=args.destination_dir,
            dry_run=args.dry_run
        )

        if success:
            logger.info("✓ Distillation completed successfully")
            return 0
        else:
            logger.error("✗ Distillation completed with errors")
            return 1

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130  # Standard exit code for Ctrl+C

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
