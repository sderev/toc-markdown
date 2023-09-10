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

## Installation

To install, use `pip` or `pipx`:

```shell
pipx install toc-markdown
```

## Integration with Vim

For a seamless experience in updating the TOC of your Markdown files through Vim, ensure the `toc-markdown` tool is either accessible from your PATH or specify its absolute path in the Vim configuration.

* Include the `toc-markdown` tool in your PATH environment variable, enabling direct execution from Vim.

   **OR**

* If the `toc-markdown` tool isn't in the PATH, specify its absolute path in the Vim configuration provided below. 

Next, add the following line to your `.vimrc` file:

```vim
autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:!toc-markdown %:p<cr>:e!<cr>
```

With this setup, simply press `<leader>t` in normal mode when editing a Markdown file in Vim. This will save the file, run the `toc-markdown` tool on it, and then reload the edited file to display the refreshed TOC.
