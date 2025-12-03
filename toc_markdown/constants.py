"""Constants used across the toc-markdown package."""

from __future__ import annotations

import re

from .config import TocConfig

DEFAULT_CONFIG = TocConfig()

# Markdown patterns
# Default header matcher; config-aware patterns are built inside the parser.
HEADER_PATTERN = re.compile(rf"^(#{{{DEFAULT_CONFIG.min_level},{DEFAULT_CONFIG.max_level}}}) (.*)$")
CODE_FENCE_PATTERN = re.compile(r"^(?P<indent>\s{0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
CLOSING_FENCE_MAX_INDENT = 3

# TOC markers and configuration defaults
TOC_START_MARKER = DEFAULT_CONFIG.start_marker
TOC_END_MARKER = DEFAULT_CONFIG.end_marker
TOC_HEADER = DEFAULT_CONFIG.header_text
MAX_HEADERS = DEFAULT_CONFIG.max_headers
MAX_TOC_SECTION_LINES = MAX_HEADERS + 100  # allow slack for TOC metadata
