#!/usr/bin/env python3
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   juniper-canopy
# Application:   juniper-canopy
# File Name:     check_doc_links.py
# Author:        Paul Calnon
# Version:       0.7.0
#
# Date Created:  2026-02-25
# Last Modified: 2026-05-18
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Validates internal links in markdown documentation files.
#    Checks that relative file links point to existing files and
#    that same-file anchor links reference existing headings.
#    External URLs (http/https/mailto) are skipped.
#
#    Cross-repo links to Juniper ecosystem siblings (../juniper-X/...) and
#    ecosystem-root links (../CLAUDE.md, ../../notes/..., etc.) are classified
#    via regex and handled according to the --cross-repo policy:
#      skip  - silently skip, report count (default for CI)
#      warn  - print warnings but do not fail
#      check - validate via filesystem (requires sibling repos on disk for
#              cross-repo links; ecosystem-root links resolve from disk)
#
# Usage:
#    python scripts/check_doc_links.py                           # Scan all .md files (cross-repo: check)
#    python scripts/check_doc_links.py --cross-repo skip         # Skip cross-repo links (CI mode)
#    python scripts/check_doc_links.py --cross-repo warn         # Warn on cross-repo links
#    python scripts/check_doc_links.py --verbose                 # Show all links checked
#    python scripts/check_doc_links.py docs/ notes/              # Scan specific directories
#    python scripts/check_doc_links.py --exclude templates       # Exclude a directory
#
# Exit Codes:
#    0 - All links valid
#    1 - Broken links found (or invalid arguments)
#
# References:
#    - RD-014: Add Documentation Build Step to CI
#    - CROSS_REPO_LINK_RESOLUTION_PROPOSAL.md
#####################################################################################################################################################################################################

"""Validate internal links in markdown documentation files.

Scans markdown files for relative links and anchor references,
verifying that target files exist and heading anchors are valid.
Cross-repo links to Juniper ecosystem siblings (``../juniper-X/...``) and
ecosystem-root links (``../CLAUDE.md``, ``../../notes/...``, etc.) are
classified and handled via the configurable ``--cross-repo`` policy
(``skip``, ``warn``, or ``check``).
"""

import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# Regex to find markdown links: [text](target)
# Captures the target (group 1) and the full match for line reporting
_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Prefixes that indicate external URLs (skip these)
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://")

# File extensions to treat as documentation
_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}

# Directories to skip during scanning
_SKIP_DIRS = {
    ".git",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".egg-info",
    "htmlcov",
    ".trunk",
    ".vscode",
    ".idea",
}

# Directories to exclude from link validation (contain expected broken links)
# - templates/: placeholder links (LINK_TO_PHASE0_README, [VERIFICATION_REPORT_FILE], etc.)
# - history/: archived PR descriptions and plans referencing old monorepo paths
_EXCLUDE_DIRS: set[str] = set()

# Juniper ecosystem repository names (hardcoded for security -- see CROSS_REPO_LINK_RESOLUTION_PROPOSAL.md)
# Auto-discovery from the filesystem is intentionally avoided to prevent a malicious directory name
# from being automatically trusted. Update this set when repos are added/removed.
_ECOSYSTEM_REPOS = {
    "juniper-canopy",
    "juniper-cascor",
    "juniper-cascor-client",
    "juniper-cascor-worker",
    "juniper-data",
    "juniper-data-client",
    "juniper-deploy",
    "juniper-ml",
}

# Pattern to detect cross-repo relative links (one or more ../ followed by an ecosystem repo name)
_CROSS_REPO_PATTERN = re.compile(r"^(?:\.\./)*(" + "|".join(re.escape(r) for r in sorted(_ECOSYSTEM_REPOS)) + r")/")

# Files and directories that live at the Juniper ecosystem root (parent of the
# juniper-X repos). Repo docs may reference them via ``../<item>`` /
# ``../../<item>`` patterns; the validator classifies these the same way as
# cross-repo links and applies the --cross-repo policy to them.
_ECOSYSTEM_ROOT_ITEMS = frozenset({
    "AGENTS.md",
    "CLAUDE.md",
    "Juniper.code-workspace",
    "Juniper1.code-workspace",
    "backups",
    "logs",
    "notes",
    "prompts",
    "resources",
    "worktrees",
    "juniper-legacy",
})

# Pattern to detect ecosystem-root relative links: one or more ../ segments
# followed by a known ecosystem-root item. Classification only applies when
# the link also escapes the current repo (verified by the bounds check at the
# call site); ``../notes/foo.md`` from a repo subdirectory that still resolves
# inside the repo is handled by normal intra-repo validation.
_ECOSYSTEM_ROOT_PATTERN = re.compile(
    r"^(?:\.\./)+(" + "|".join(re.escape(n) for n in sorted(_ECOSYSTEM_ROOT_ITEMS)) + r")(?:/|$)"
)

# Maximum allowed directory traversal segments (..) in a single link
_MAX_TRAVERSAL_DEPTH = 5

# Valid modes for --cross-repo flag
_CROSS_REPO_MODES = {"skip", "warn", "check"}


def _is_ecosystem_root(candidate: Path) -> bool:
    """Check if a directory appears to be the Juniper ecosystem root.

    A directory is considered the ecosystem root if it contains at least 3
    known sibling repos from ``_ECOSYSTEM_REPOS``.

    Args:
        candidate: Directory path to check.

    Returns:
        True if the directory contains 3+ known ecosystem repos.
    """
    found = sum(1 for repo in _ECOSYSTEM_REPOS if (candidate / repo).is_dir())
    return found >= 3


def _discover_ecosystem_root(repo_root: Path) -> Path | None:
    """Attempt to find the Juniper ecosystem parent directory.

    Uses two methods:
    1. Git common directory detection — ``git rev-parse --git-common-dir``
       returns the main repo's ``.git`` directory even from worktrees
       (including ``.claude/worktrees/`` and centralized worktrees).
       The ecosystem root is the parent of the main repo root.
    2. Walking up from repo_root (limited to 2 levels) as a fallback
       when git is not available.

    Args:
        repo_root: The repository root directory.

    Returns:
        Path to ecosystem root directory, or None if not found.
    """
    # Method 1: Use git common dir to find the main repo root
    # This handles all worktree types (.claude/worktrees/, centralized, standard)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode == 0:
            git_common_dir = Path(result.stdout.strip())
            if not git_common_dir.is_absolute():
                git_common_dir = (repo_root / git_common_dir).resolve()
            main_repo_root = git_common_dir.parent
            candidate = main_repo_root.parent
            if _is_ecosystem_root(candidate):
                return candidate
    except FileNotFoundError:
        pass

    # Method 2: Walk up from repo_root (limited depth, fallback)
    for parent in [repo_root.parent, repo_root.parent.parent]:
        if _is_ecosystem_root(parent):
            return parent

    return None


def _heading_to_anchor(heading_text: str) -> str:
    """Convert a markdown heading to its GitHub-style anchor ID.

    GitHub anchor generation rules:
    - Convert to lowercase
    - Remove punctuation (except hyphens and spaces)
    - Replace spaces with hyphens
    - Strip leading/trailing hyphens

    Args:
        heading_text: The heading text (without the # prefix).

    Returns:
        The anchor string (without the leading #).
    """
    text = heading_text.strip().lower()
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Remove characters that aren't alphanumeric, spaces, or hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace each whitespace character with a hyphen (preserves double-space → --)
    text = re.sub(r"\s", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def _extract_headings(content: str) -> set[str]:
    """Extract all heading anchors from markdown content.

    Args:
        content: The markdown file content.

    Returns:
        Set of anchor strings (without leading #).
    """
    anchors = set()
    for line in content.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            heading_text = match.group(2).strip()
            anchors.add(_heading_to_anchor(heading_text))
    return anchors


def _find_markdown_files(search_paths: list[Path], repo_root: Path, exclude_dirs: set[str] | None = None) -> list[Path]:
    """Find all markdown files in the given paths.

    Args:
        search_paths: Directories or files to scan.
        repo_root: Repository root for default scanning.
        exclude_dirs: Additional directory names to exclude.

    Returns:
        Sorted list of markdown file paths.
    """
    skip = _SKIP_DIRS | (exclude_dirs or set()) | _EXCLUDE_DIRS
    md_files: dict[Path, Path] = {}  # realpath -> first display path encountered

    def _add(display_path: Path) -> None:
        # Dedupe by resolved (real) path so a file reachable both directly and
        # via a symlink is only validated once. Without this, a file like
        # ``notes/development/<name>.md`` that is a symlink to ``notes/<name>.md``
        # gets scanned twice with two different relative-path resolution roots,
        # producing spurious "broken link" reports for any link that happens to
        # resolve correctly from one location but not the other.
        real = display_path.resolve()
        if real not in md_files:
            md_files[real] = display_path

    for path in search_paths:
        if path.is_file() and path.suffix in _DOC_EXTENSIONS:
            # Skip broken symlinks
            if path.is_symlink() and not path.exists():
                continue
            # Check if file is under an excluded directory
            try:
                rel = path.relative_to(repo_root)
                if not any(part in skip for part in rel.parts):
                    _add(path)
            except ValueError:
                _add(path)
        elif path.is_dir():
            for ext in _DOC_EXTENSIONS:
                for f in path.rglob(f"*{ext}"):
                    # Skip broken symlinks
                    if f.is_symlink() and not f.exists():
                        continue
                    try:
                        rel = f.relative_to(repo_root)
                        if not any(part in skip for part in rel.parts):
                            _add(f)
                    except ValueError:
                        if not any(part in skip for part in f.parts):
                            _add(f)

    return sorted(md_files.values())


def _validate_cross_repo_structure(file_part: str) -> str | None:
    """Validate that a cross-repo link doesn't traverse back out of its target repo.

    Even in skip mode, structurally malformed cross-repo links are rejected.
    This prevents patterns like ``../juniper-data/../../etc/passwd`` from being
    silently skipped.

    Args:
        file_part: The file path portion of the link target.

    Returns:
        Error message string if structural validation fails, None if valid.
    """
    parts = Path(file_part).parts
    for i, part in enumerate(parts):
        if part in _ECOSYSTEM_REPOS:
            remainder = Path(*parts[i + 1 :]) if i + 1 < len(parts) else Path(".")
            if ".." in remainder.parts:
                return f"cross-repo link escapes target repository: {file_part}"
            break
    return None


def _validate_file(md_file: Path, repo_root: Path, verbose: bool = False, cross_repo_mode: str = "check", ecosystem_root: Path | None = None) -> tuple[list[str], int]:
    """Validate all internal links in a single markdown file.

    Args:
        md_file: Path to the markdown file.
        repo_root: Repository root for resolving relative paths.
        verbose: If True, print each link checked.
        cross_repo_mode: How to handle cross-repo links ("skip", "warn", or "check").
        ecosystem_root: Path to the Juniper ecosystem parent directory. Required for
            cross-repo link validation in "check" mode.

    Returns:
        Tuple of (error messages list, cross-repo links skipped/warned count).
    """
    errors = []
    cross_repo_skipped = 0
    content = md_file.read_text(encoding="utf-8", errors="replace")
    headings = _extract_headings(content)
    file_dir = md_file.parent
    repo_boundary = repo_root.resolve()

    code_fence = None
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped_line = line.strip()

        # Track fenced code blocks (``` or ~~~) -- skip all content inside
        if code_fence is None:
            fence_match = re.match(r"^(`{3,}|~{3,})", stripped_line)
            if fence_match:
                code_fence = fence_match.group(1)
                continue
        else:
            close_match = re.match(r"^(`{3,}|~{3,})\s*$", stripped_line)
            if close_match and close_match.group(1)[0] == code_fence[0] and len(close_match.group(1)) >= len(code_fence):
                code_fence = None
            continue

        # Strip inline code spans before checking for links
        check_line = re.sub(r"`[^`]+`", "", line)

        for match in _LINK_PATTERN.finditer(check_line):
            link_text = match.group(1)
            target = match.group(2).strip()

            # Skip external URLs
            if any(target.startswith(prefix) for prefix in _EXTERNAL_PREFIXES):
                if verbose:
                    print(f"  SKIP (external): {md_file}:{line_num} -> {target}")
                continue

            # Skip image badges and data URIs
            if target.startswith("data:") or target.startswith("//"):
                continue

            # Parse target into file path and optional anchor
            if "#" in target:
                file_part, anchor = target.split("#", 1)
            else:
                file_part = target
                anchor = None

            # Same-file anchor link
            if not file_part:
                if anchor and anchor not in headings:
                    errors.append(f"  {md_file}:{line_num}: broken anchor #{anchor} (heading not found)")
                elif verbose:
                    print(f"  OK (anchor): {md_file}:{line_num} -> #{anchor}")
                continue

            # --- Input validation ---

            rel_source = md_file.relative_to(repo_root)

            # Reject null bytes (path truncation attacks)
            if "\x00" in file_part:
                errors.append(f"  {rel_source}:{line_num}: null byte in link target")
                continue

            # Reject absolute paths (must always be relative)
            if Path(file_part).is_absolute():
                errors.append(f"  {rel_source}:{line_num}: absolute path in documentation link (must be relative)")
                continue

            # Traversal depth limit
            if file_part.count("..") > _MAX_TRAVERSAL_DEPTH:
                errors.append(f"  {rel_source}:{line_num}: excessive directory traversal in link")
                continue

            # --- Cross-repo link classification ---

            cross_repo_match = _CROSS_REPO_PATTERN.match(file_part)
            if cross_repo_match:
                # Structural validation even in skip/warn mode
                structural_error = _validate_cross_repo_structure(file_part)
                if structural_error:
                    errors.append(f"  {rel_source}:{line_num}: {structural_error}")
                    continue

                if cross_repo_mode == "skip":
                    cross_repo_skipped += 1
                    if verbose:
                        print(f"  SKIP (cross-repo): {md_file}:{line_num} -> {file_part}")
                    continue
                elif cross_repo_mode == "warn":
                    cross_repo_skipped += 1
                    print(f"  WARN (cross-repo): {rel_source}:{line_num} -> {file_part}")
                    continue
                # "check" mode: resolve against ecosystem root
                elif ecosystem_root is not None:
                    repo_name = cross_repo_match.group(1)
                    intra_repo_path = file_part[cross_repo_match.end() :]
                    target_path = (ecosystem_root / repo_name / intra_repo_path).resolve()
                    target_repo_boundary = (ecosystem_root / repo_name).resolve()

                    if not target_path.is_relative_to(target_repo_boundary):
                        errors.append(f"  {rel_source}:{line_num}: cross-repo link escapes target repository boundary")
                        continue

                    if target_path.exists():
                        if verbose:
                            print(f"  OK (cross-repo): {md_file}:{line_num} -> {file_part}")
                    else:
                        errors.append(f"  {rel_source}:{line_num}: broken link [{link_text}]({target}) -> file not found in {repo_name}")
                    continue
                # "check" mode without ecosystem root falls through to normal validation

            # --- Resolve and validate file path ---

            target_path = (file_dir / file_part).resolve()
            target_path_from_root = (repo_root / file_part).resolve()

            # Bounds check: ensure at least one resolution stays within repo
            file_relative_in_bounds = target_path.is_relative_to(repo_boundary)
            root_relative_in_bounds = target_path_from_root.is_relative_to(repo_boundary)

            if not file_relative_in_bounds and not root_relative_in_bounds:
                # Path escapes the repo. If it lands on a known ecosystem-root
                # item (CLAUDE.md, notes/, etc.), classify it the same way as
                # a cross-repo link and apply the --cross-repo policy. This is
                # the only valid reason for a relative link to leave the repo;
                # anything else is a real broken link.
                eco_match = _ECOSYSTEM_ROOT_PATTERN.match(file_part)
                if eco_match:
                    if cross_repo_mode == "skip":
                        cross_repo_skipped += 1
                        if verbose:
                            print(f"  SKIP (ecosystem-root): {md_file}:{line_num} -> {file_part}")
                        continue
                    elif cross_repo_mode == "warn":
                        cross_repo_skipped += 1
                        print(f"  WARN (ecosystem-root): {rel_source}:{line_num} -> {file_part}")
                        continue
                    # "check" mode: verify the target exists on disk relative
                    # to the source file. ecosystem_root is informational only
                    # for the error message; resolution is purely path-based
                    # so this works without sibling repos checked out.
                    if target_path.exists() or target_path_from_root.exists():
                        if verbose:
                            print(f"  OK (ecosystem-root): {md_file}:{line_num} -> {file_part}")
                    else:
                        errors.append(
                            f"  {rel_source}:{line_num}: broken ecosystem-root link "
                            f"[{link_text}]({target}) -> file not found"
                        )
                    continue

                errors.append(f"  {rel_source}:{line_num}: link resolves outside repository boundary")
                continue

            # Check existence only for in-bounds paths
            file_exists = file_relative_in_bounds and target_path.exists()
            root_exists = root_relative_in_bounds and target_path_from_root.exists()

            if file_exists or root_exists:
                if verbose:
                    print(f"  OK (file): {md_file}:{line_num} -> {file_part}")
            else:
                errors.append(f"  {rel_source}:{line_num}: broken link [{link_text}]({target}) -> file not found")

    return errors, cross_repo_skipped


def main() -> int:
    """Run documentation link validation.

    Returns:
        0 if all links are valid, 1 if broken links found or invalid arguments.
    """
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    exclude_dirs: set[str] = set()
    cross_repo_mode = "check"

    # Parse flags
    argv = sys.argv[1:]
    positional = []
    i = 0
    while i < len(argv):
        if argv[i] == "--exclude" and i + 1 < len(argv):
            exclude_dirs.add(argv[i + 1])
            i += 2
        elif argv[i].startswith("--exclude="):
            exclude_dirs.add(argv[i].split("=", 1)[1])
            i += 1
        elif argv[i] == "--cross-repo" and i + 1 < len(argv):
            cross_repo_mode = argv[i + 1]
            if cross_repo_mode not in _CROSS_REPO_MODES:
                print(f"ERROR: --cross-repo must be one of: {', '.join(sorted(_CROSS_REPO_MODES))}")
                return 1
            i += 2
        elif argv[i].startswith("--cross-repo="):
            cross_repo_mode = argv[i].split("=", 1)[1]
            if cross_repo_mode not in _CROSS_REPO_MODES:
                print(f"ERROR: --cross-repo must be one of: {', '.join(sorted(_CROSS_REPO_MODES))}")
                return 1
            i += 1
        elif not argv[i].startswith("-"):
            positional.append(argv[i])
            i += 1
        else:
            i += 1

    # Determine repo root (script is in scripts/ subdir)
    repo_root = Path(__file__).resolve().parent.parent

    # Determine search paths
    if positional:
        search_paths = [repo_root / a for a in positional]
    else:
        # Default: scan all markdown files in the repo
        search_paths = [repo_root]

    # Discover ecosystem root for cross-repo check mode
    ecosystem_root = None
    if cross_repo_mode == "check":
        ecosystem_root = _discover_ecosystem_root(repo_root)
        if ecosystem_root is None:
            print("WARNING: Ecosystem root not found. Cross-repo links will be skipped.")
            print("  (Ensure sibling repos are checked out as siblings, or use --cross-repo skip)")
            cross_repo_mode = "skip"

    print("=" * 60)
    print("Documentation Link Validation")
    print("=" * 60)
    if exclude_dirs:
        print(f"Excluding directories: {', '.join(sorted(exclude_dirs))}")
    if cross_repo_mode != "check":
        print(f"Cross-repo links: {cross_repo_mode}")
    elif ecosystem_root is not None:
        print(f"Cross-repo links: check (ecosystem root: {ecosystem_root})")

    md_files = _find_markdown_files(search_paths, repo_root, exclude_dirs)
    print(f"\nScanning {len(md_files)} markdown files...\n")

    all_errors = []
    files_with_errors = 0
    total_cross_repo_skipped = 0

    for md_file in md_files:
        errors, cross_repo_skipped = _validate_file(md_file, repo_root, verbose=verbose, cross_repo_mode=cross_repo_mode, ecosystem_root=ecosystem_root)
        if errors:
            files_with_errors += 1
            all_errors.extend(errors)
        total_cross_repo_skipped += cross_repo_skipped

    # Report results
    print("-" * 60)
    if total_cross_repo_skipped > 0:
        action = "skipped" if cross_repo_mode == "skip" else "warned"
        print(f"\nCross-repo links {action}: {total_cross_repo_skipped}")
    if all_errors:
        print(f"\nFOUND {len(all_errors)} broken link(s) in {files_with_errors} file(s):\n")
        for error in all_errors:
            print(error)
        print(f"\n{'=' * 60}")
        print("FAILED: Documentation link validation")
        print(f"{'=' * 60}")
        return 1
    else:
        print(f"\nAll links valid across {len(md_files)} files.")
        print(f"\n{'=' * 60}")
        print("PASSED: Documentation link validation")
        print(f"{'=' * 60}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
