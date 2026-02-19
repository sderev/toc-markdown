# Markdown Table of Contents Generator

Generates a table of contents (TOC) for Markdown files. Detects headers and creates a linked TOC. Updates existing TOCs in-place when markers are present; otherwise prints to stdout.

![toc_markdown](https://github.com/sderev/toc-markdown/assets/24412384/a733d430-40fd-4671-b22f-cdc3dcf7bf52)

<!-- TOC -->
## Table of Contents

1. [Quick Start](#quick-start)
1. [Features](#features)
1. [Installation](#installation)
1. [Usage](#usage)
1. [Configuration](#configuration)
1. [Integration with Vim](#integration-with-vim)
<!-- /TOC -->

## Quick Start

Add TOC markers to your Markdown file:

```md
<!-- TOC -->
<!-- /TOC -->
```

Run:

```bash
toc-markdown README.md
```

The TOC appears between the markers. Run again to update.

Without markers, the TOC prints to stdout for manual insertion.

## Features

* Generates a table of contents from Markdown headers.
* Updates existing TOCs between markers or prints to stdout.
* Supports headings from levels 2 to 3 by default (configurable).
* Provides clickable links to sections.
* Preserves file structure and formatting.

## Installation

**Requirements**: Python 3.11+

Using `uv` (recommended):

```bash
uv tool install toc-markdown
```

Using `pip`:

```bash
pip install toc-markdown
```

## Usage

Run `toc-markdown` on a `.md` or `.markdown` file:

```bash
# Update file in-place (requires TOC markers)
toc-markdown path/to/file.md

# Print TOC to stdout (no markers in file)
toc-markdown path/to/file.md

# Customize header levels
toc-markdown README.md --min-level 1 --max-level 4

# Change list style
toc-markdown README.md --list-style "*"
toc-markdown README.md --list-style "-"

# Custom header text
toc-markdown README.md --header-text "## Contents"

# Preserve Unicode in slugs
toc-markdown README.md --preserve-unicode

# Custom indentation
toc-markdown README.md --indent-chars "  "

# Custom markers
toc-markdown README.md --start-marker "<!-- BEGIN TOC -->" --end-marker "<!-- END TOC -->"
```

### Safety Limits

* Only regular Markdown files (`.md`, `.markdown`) are accepted.
* Run from the directory tree that owns the target file. Files outside the working directory are rejected.
* Symlinks are refused.
* Files larger than 10 MiB are rejected. Increase via `max_file_size` in config or `TOC_MARKDOWN_MAX_FILE_SIZE` environment variable (up to 100 MiB).
* Lines longer than 10,000 characters are rejected. Increase via `max_line_length` in config or `TOC_MARKDOWN_MAX_LINE_LENGTH` environment variable.
* Files with more than 10,000 headers are rejected. Increase via `max_headers` in config.
* Files must be valid UTF-8.
* Updates use atomic writes via temporary files.

Run `toc-markdown --help` for all options.

## Configuration

Create `.toc-markdown.toml` in your project root:

```toml
[toc-markdown]
min_level = 2
max_level = 3
list_style = "1."
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `start_marker` | `<!-- TOC -->` | Opening marker |
| `end_marker` | `<!-- /TOC -->` | Closing marker |
| `header_text` | `## Table of Contents` | TOC heading |
| `min_level` | `2` | Minimum header level to include |
| `max_level` | `3` | Maximum header level to include |
| `list_style` | `1.` | Bullet style: `1.`, `*`, `-`, `ordered`, `unordered` |
| `indent_chars` | `    ` (4 spaces) | Indentation for nested entries |
| `indent_spaces` | `null` | Alternative to `indent_chars`; sets spaces count |
| `preserve_unicode` | `false` | Keep Unicode in slugs |
| `max_file_size` | `10485760` (10 MiB) | Maximum file size in bytes |
| `max_line_length` | `10000` | Maximum line length |
| `max_headers` | `10000` | Maximum headers to process |

CLI flags override config file values.

## Integration with Vim

Example mapping (for files with TOC markers):

```vim
autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:silent !toc-markdown %:p<cr>:e<cr>
```

Press `<leader>t` in normal mode to save, update the TOC, and reload the buffer.

For files without markers (insert TOC at cursor):

```vim
autocmd FileType markdown nnoremap <buffer> <leader>T :r !toc-markdown %:p<cr>
```
