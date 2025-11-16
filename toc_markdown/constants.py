"""Constants used across the toc-markdown package."""

from __future__ import annotations

import re

# Markdown patterns
HEADER_PATTERN = re.compile(r"^(#{2,3}) (.*)$")
CODE_FENCE_PATTERN = re.compile(r"^(?P<indent>\s{0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
CLOSING_FENCE_MAX_INDENT = 3

# TOC markers and configuration
TOC_START_MARKER = "<!-- TOC -->"
TOC_END_MARKER = "<!-- /TOC -->"
TOC_HEADER = "## Table of Contents"
MAX_HEADERS = 10_000
MAX_TOC_SECTION_LINES = MAX_HEADERS + 100  # allow slack for TOC metadata
