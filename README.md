# Markdown Table of Contents Generator

This tool scans Markdown files to detect headers and subsequently creates a Table of Contents (TOC) with direct links to the respective sections. It either updates an existing TOC or generates a new one if none is found.

![toc_markdown](https://github.com/sderev/toc-markdown/assets/24412384/a733d430-40fd-4671-b22f-cdc3dcf7bf52)

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Installation](#installation)
1. [Integration with Vim](#integration-with-vim)
<!-- /TOC -->

## Features

* Automatically generates a table of contents for your Markdown files.
* Either updates an existing TOC or inserts a new one if absent.
* Supports headers of levels 2 to 3.
* Provides clickable links leading to the corresponding sections within the document.
* Preserves the structure and formatting of the Markdown file.
* Guards against unsafe inputs: symlinks are rejected, files must live under the current working directory, and data is re-read before any write to prevent race conditions.

## Installation

**Requirements**: Python 3.10+

To install, use `uv` (recommended) or `pip`:

```shell
# Using uv (recommended)
uv tool install toc-markdown

# Using pip
pip install toc-markdown
```

## Usage & Safety

* Only regular Markdown files (`.md`, `.markdown`) are accepted.
* Run the CLI from the directory tree that owns the target file—files outside the current working directory are rejected to prevent path traversal.
* Symlinks (whether the target or any parent path) are refused.
* Files larger than 10 MiB are rejected. Override via `TOC_MARKDOWN_MAX_FILE_SIZE=<bytes>` if you need a higher cap.
* Files must be valid UTF-8. Invalid byte sequences abort processing to avoid corrupt output.
* Updates happen through a temporary file in the same directory; contents are flushed, synced, and atomically swapped while preserving permissions.

## Integration with Vim

Add the following line to your `.vimrc` file:

```vim
autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:.!toc-markdown %:p<cr>
```

With this setup, simply press `<leader>t` in normal mode when editing a Markdown file in Vim. This will save the file and run `toc-markdown` on it.

## Development

Install the project (editable) together with the development dependencies using `uv`:

```shell
uv venv
uv pip install -e ".[dev]"
```

Run the test suite (unit, integration, Hypothesis, security) with coverage:

```shell
uv run pytest tests/ --cov=toc_markdown --cov-report=html
```

The HTML coverage report is written to `htmlcov/index.html`. The suite currently exercises 100% of the codebase.

### Fuzz Testing (Optional)

Fuzz tests using atheris are available but only work on Python 3.10-3.11 (atheris 2.3.0 is incompatible with Python 3.12+):

```shell
# Install fuzz dependencies (Python 3.10-3.11 only)
uv pip install -e ".[fuzz]"

# Run all tests including fuzz tests
uv run pytest tests/ --cov=toc_markdown
```

