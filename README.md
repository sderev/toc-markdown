# Markdown Table of Contents Generator

This Python script automates the generation and management of a Table of Contents (TOC) for your Markdown files. It scans the Markdown file for headers and creates a TOC with clickable links to the respective sections. The script can replace an existing TOC or insert a new one if none exists.

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
* Supports headers of levels 1 to 3.
* Generates clickable links to the corresponding sections within the document.
* Maintains the structure and formatting of the Markdown file.

## Getting Started

### Prerequisites

* Python 3.x

### Installation

```shell
git clone https://github.com/your-username/markdown-toc-generator.git
```

### Integration with Vim

To streamline the process of updating the TOC in your Markdown files, ensure that the `toc_markdown` script is either accessible from your PATH or provide its absolute path in the Vim configuration.

* Add the directory containing the `toc_markdown` script to your PATH environment variable. This step allows Vim to execute the script directly.

   **OR**

* If the `toc_markdown` script is not in the PATH, provide its absolute path in the Vim configuration. Open your `.vimrc` file and add the following line:

   ```vim
   autocmd FileType markdown nnoremap <buffer> <leader>t :w<cr>:.!toc_markdown %:p<cr>
   ```

   Replace `path/to/toc_markdown` with the actual absolute path to the `toc_markdown` script on your system.

With the above configuration, you can press `<leader>t` while in normal mode within a Markdown file in Vim. It will save the file, execute the `toc_markdown` script on it, and reload the updated file, displaying the updated TOC.

Make sure you have the `toc_markdown` script accessible from your PATH or provide its absolute path correctly for this integration to work.