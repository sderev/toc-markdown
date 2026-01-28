# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [scriv](https://scriv.readthedocs.io/) to manage the changelog.
Fragments are collected in `changelog.d/` and compiled into this file at release time.

<!-- scriv-insert-here -->

# 2026-01-28

## Security

* Add line length and header count limits to prevent DoS attacks. Configurable via `TOC_MARKDOWN_MAX_LINE_LENGTH` environment variable.
* Harden `parse_file` against file-size DoS with 100MiB hard cap.
* Detect concurrent edits before file replacement.
* Fix TOC marker detection in code blocks to prevent bypassing validation.

## Feature

* Add GitHub-style duplicate slug handling to `generate_toc()`. Duplicate headers now generate unique anchor slugs with numeric suffixes (`#intro`, `#intro-1`, `#intro-2`).
* Add `.toc-markdown.toml` configuration file support. Lookups search parent directories up to repository root.
* Add `--preserve-unicode` flag to preserve Unicode characters in slugs instead of transliterating them. Supports tri-state CLI flags to respect config values.

* Strip markdown links from TOC header titles to keep TOC clean. Extracts link text from inline links, reference-style links, and image links while preserving inline code.
* Implement atomic file updates using `tempfile` and `os.replace()` for safer file operations.

* Preserve file ownership (`uid`/`gid`) and access time (`atime`) during TOC updates. Modification time intentionally updated to reflect actual changes.

## Bugfix

* Match `header_text` exactly when skipping headings. Replaces `startswith` with full-line match to prevent false positives.
