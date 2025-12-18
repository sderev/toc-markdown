# Markdown Table of Contents Generator

This tool scans Markdown files to detect headers and generates a Table of Contents (TOC) with links to the respective sections. If the file already contains TOC markers, it updates the TOC in-place; otherwise it prints a TOC to stdout.

![toc_markdown](https://github.com/sderev/toc-markdown/assets/24412384/a733d430-40fd-4671-b22f-cdc3dcf7bf52)

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Installation](#installation)
1. [Usage](#usage)
1. [Configuration](#configuration)
1. [Integration with Vim](#integration-with-vim)
<!-- /TOC -->

## Features

* Automatically generates a table of contents for your Markdown files.
* Updates an existing TOC between markers, or prints one to stdout.
* Supports headings from levels 2 to 3 by default.
* Provides clickable links leading to the corresponding sections within the document.
* Preserves the structure and formatting of the Markdown file.

## Installation

**Requirements**: Python 3.11+

To install, use `uv` (recommended) or `pip`:

```bash
# Using uv (recommended)
uv tool install toc-markdown

# Using pip
pip install toc-markdown
```

## Usage

Run `toc-markdown` from your project directory on a `.md`/`.markdown` file.

To update a file in-place, add the markers once where you want the TOC:

```md
<!-- TOC -->
<!-- /TOC -->
```

Then run:

```bash
toc-markdown path/to/file.md
```

If the file does not contain markers, `toc-markdown` prints the generated TOC to stdout so you can paste it where you want.

Safety limits:

* Only regular Markdown files (`.md`, `.markdown`) are accepted.
* Run the CLI from the directory tree that owns the target file—files outside the current working directory are rejected to prevent path traversal.
* Symlinks (whether the target or any parent path) are refused.
* Files larger than 10 MiB are rejected. Increase the cap via `max_file_size` or `TOC_MARKDOWN_MAX_FILE_SIZE=<bytes>` (up to 100 MiB).
* Files must be valid UTF-8. Invalid byte sequences abort processing to avoid corrupt output.
* Updates happen through a temporary file in the same directory; contents are flushed, synced, and atomically swapped while preserving permissions.

## Configuration

No configuration is required.

To set defaults for a project, create a `.toc-markdown.toml` file (for example in your repo root):

```toml
[toc-markdown]
min_level = 2
max_level = 3
list_style = "1."
```

For one-off overrides, use CLI flags:

```bash
toc-markdown README.md --max-level 4 --list-style "-"
```

Run `toc-markdown --help` for the full list of options.

## Integration with Vim

Example mapping for Vim (pick any keybind you like):

```vim
autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:.!toc-markdown %:p<cr>
```

With this setup, simply press `<leader>t` in normal mode when editing a Markdown file in Vim. This will save the file and run `toc-markdown` on it.
