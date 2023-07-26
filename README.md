# Markdown Table of Contents Generator

This Python script automates the generation and management of a Table of Contents (TOC) for your Markdown files. It scans the Markdown file for headers and creates a TOC with clickable links to the respective sections. The script can update an existing TOC or insert a new one if none exists.

![toc_markdown](https://github.com/sderev/toc-markdown/assets/24412384/a733d430-40fd-4671-b22f-cdc3dcf7bf52)

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Getting Started](#getting-started)
    1. [Prerequisites](#prerequisites)
    1. [Installation](#installation)
1. [Integration with Vim](#integration-with-vim)
<!-- /TOC -->

## Features

* Automatic generation of a table of contents for your Markdown files.
* Updates an existing TOC or inserts a new one if not present.
* Supports headers of levels 2 to 3.
* Generates clickable links to the corresponding sections within the document.
* Maintains the structure and formatting of the Markdown file.

## Getting Started

### Prerequisites

* Python 3.6

### Installation

```shell
git clone https://github.com/sderev/toc-markdown.git
```

## Integration with Vim

To streamline the process of updating the TOC in your Markdown files, ensure that the `toc-markdown` script is either accessible from your PATH or provide its absolute path in the Vim configuration.

* Add the `toc-markdown` script to your PATH environment variable. This step allows Vim to execute the script directly.

   **OR**

* If the `toc-markdown` script is not in the PATH, provide its absolute path in the Vim configuration below. 

Then, open your `.vimrc` file and add the following line:

```vim
autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:!toc-markdown %:p<cr>:e!<cr>
```

With the above configuration, you can press `<leader>t` while in normal mode within a Markdown file in Vim. It will save the file, execute the `toc-markdown` script on it, and reload the updated file, displaying the updated TOC.
