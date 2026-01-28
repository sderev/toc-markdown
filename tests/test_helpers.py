import os
import socket
import stat
from pathlib import Path

import pytest

from toc_markdown.config import MAX_CONFIGURED_FILE_SIZE
from toc_markdown.filesystem import (
    collect_file_stat,
    contains_symlink,
    get_max_file_size,
    get_max_line_length,
    normalize_filepath,
    safe_read,
)
from toc_markdown.parser import strip_markdown_links


def test_get_max_file_size_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", "invalid")
    with pytest.raises(ValueError):
        get_max_file_size()


def test_get_max_file_size_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", "0")
    with pytest.raises(ValueError):
        get_max_file_size()


def test_get_max_file_size_rejects_too_large(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_FILE_SIZE", str(MAX_CONFIGURED_FILE_SIZE + 1))
    with pytest.raises(ValueError) as exc_info:
        get_max_file_size()
    assert "TOC_MARKDOWN_MAX_FILE_SIZE must be <=" in str(exc_info.value)


def test_get_max_line_length_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_LINE_LENGTH", "invalid")
    with pytest.raises(ValueError):
        get_max_line_length()


def test_get_max_line_length_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("TOC_MARKDOWN_MAX_LINE_LENGTH", "0")
    with pytest.raises(ValueError):
        get_max_line_length()


def test_normalize_filepath_missing_file(tmp_path: Path):
    with pytest.raises(ValueError):
        normalize_filepath(str(tmp_path / "missing.md"), tmp_path)


def test_normalize_filepath_handles_oserror(monkeypatch, tmp_path: Path):
    target = tmp_path / "doc.md"
    target.write_text("## Heading\n", encoding="utf-8")
    base_dir = tmp_path
    original_resolve = Path.resolve

    def _raise_oserror(self, strict=True):
        if self == target:
            raise OSError("resolve boom")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _raise_oserror)
    with pytest.raises(ValueError):
        normalize_filepath(str(target), base_dir)


def test_normalize_filepath_rejects_directory(tmp_path: Path):
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(ValueError):
        normalize_filepath(str(folder), tmp_path)


def test_contains_symlink_handles_oserror(monkeypatch, tmp_path: Path):
    probe = tmp_path / "probe.md"
    probe.write_text("## Heading\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    call_count = {"count": 0}

    def _flaky_is_symlink(self):
        if self == probe and call_count["count"] == 0:
            call_count["count"] += 1
            raise OSError("stat boom")
        return original_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", _flaky_is_symlink)
    assert contains_symlink(probe) is False


def test_collect_file_stat_handles_missing_file(tmp_path: Path):
    with pytest.raises(IOError):
        collect_file_stat(tmp_path / "missing.md")


def test_collect_file_stat_rejects_symlink(tmp_path: Path):
    target = tmp_path / "actual.md"
    target.write_text("## Heading\n", encoding="utf-8")
    link = tmp_path / "alias.md"
    os.symlink(target, link)

    with pytest.raises(IOError):
        collect_file_stat(link)


def test_collect_file_stat_rejects_directory(tmp_path: Path):
    directory = tmp_path / "folder"
    directory.mkdir()
    with pytest.raises(IOError):
        collect_file_stat(directory)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo not available")
def test_collect_file_stat_rejects_fifo(tmp_path: Path):
    """Test that FIFOs are rejected at the collect_file_stat level."""
    fifo = tmp_path / "pipe.md"
    try:
        os.mkfifo(fifo)
    except OSError:  # pragma: no cover
        pytest.skip("Unable to create FIFO")

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(fifo)
    assert "is not a regular file" in str(exc_info.value)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix sockets not available")
def test_collect_file_stat_rejects_socket(tmp_path: Path):
    """Test that Unix sockets are rejected at the collect_file_stat level."""
    socket_path = tmp_path / "socket.md"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(socket_path))
    except OSError:  # pragma: no cover
        pytest.skip("Unable to create socket")
    finally:
        sock.close()

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(socket_path)
    assert "is not a regular file" in str(exc_info.value)


def test_collect_file_stat_rejects_mocked_character_device(tmp_path: Path, monkeypatch):
    """Test that character devices are rejected using mocked stat."""
    device = tmp_path / "device.md"
    device.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return character device mode
    original_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device):
            # Create a mock stat_result with S_IFCHR bit set
            class MockStatResult:
                st_mode = stat.S_IFCHR | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, "st_uid") else 0
                st_gid = result.st_gid if hasattr(result, "st_gid") else 0
                st_ino = result.st_ino if hasattr(result, "st_ino") else 0
                st_dev = result.st_dev if hasattr(result, "st_dev") else 0

            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(device)
    assert "is not a regular file" in str(exc_info.value)


def test_collect_file_stat_rejects_mocked_block_device(tmp_path: Path, monkeypatch):
    """Test that block devices are rejected using mocked stat."""
    device = tmp_path / "block.md"
    device.write_text("# Content\n", encoding="utf-8")

    # Mock os.stat to return block device mode
    original_stat = os.stat

    def mock_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if str(path) == str(device):
            # Create a mock stat_result with S_IFBLK bit set
            class MockStatResult:
                st_mode = stat.S_IFBLK | 0o666
                st_size = result.st_size
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns
                st_atime = result.st_atime
                st_atime_ns = result.st_atime_ns
                st_uid = result.st_uid if hasattr(result, "st_uid") else 0
                st_gid = result.st_gid if hasattr(result, "st_gid") else 0
                st_ino = result.st_ino if hasattr(result, "st_ino") else 0
                st_dev = result.st_dev if hasattr(result, "st_dev") else 0

            return MockStatResult()
        return result

    monkeypatch.setattr(os, "stat", mock_stat)

    with pytest.raises(IOError) as exc_info:
        collect_file_stat(device)
    assert "is not a regular file" in str(exc_info.value)


def test_safe_read_raises_for_directory(tmp_path: Path):
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(IOError):
        safe_read(directory)


def test_strip_markdown_links_single_link():
    """Test stripping a single markdown link."""
    assert strip_markdown_links("[Link Text](https://example.com)") == "Link Text"


def test_strip_markdown_links_with_surrounding_text():
    """Test stripping links while preserving surrounding text."""
    assert strip_markdown_links("See [Link](url) for details") == "See Link for details"


def test_strip_markdown_links_multiple_links():
    """Test stripping multiple links from the same string."""
    text = "[First](url1) and [Second](url2)"
    assert strip_markdown_links(text) == "First and Second"


def test_strip_markdown_links_no_links():
    """Test that text without links is unchanged."""
    assert strip_markdown_links("Plain text") == "Plain text"


def test_strip_markdown_links_brackets_without_url():
    """Test that brackets without parentheses are preserved."""
    assert strip_markdown_links("Text with [brackets] only") == "Text with [brackets] only"


def test_strip_markdown_links_parentheses_without_brackets():
    """Test that parentheses without brackets are preserved."""
    assert strip_markdown_links("Text (with parens)") == "Text (with parens)"


def test_strip_markdown_links_empty_link_text():
    """Test handling of empty link text."""
    assert strip_markdown_links("[](https://example.com)") == ""


def test_strip_markdown_links_complex_url():
    """Test stripping links with complex URLs."""
    text = "[Title](https://example.com/path?param=value&other=123#anchor)"
    assert strip_markdown_links(text) == "Title"


def test_strip_markdown_links_nested_brackets_in_text():
    """Test link text containing balanced nested brackets."""
    # The state machine now handles balanced nested brackets correctly.
    result = strip_markdown_links("[Text [with] brackets](url)")
    assert result == "Text [with] brackets"


def test_strip_markdown_links_special_characters_in_text():
    """Test link text with special characters."""
    assert strip_markdown_links("[Café & Résumé](url)") == "Café & Résumé"


def test_strip_markdown_links_mixed_content():
    """Test mixed content with links and plain text."""
    text = "Start [Link1](url1) middle [Link2](url2) end"
    assert strip_markdown_links(text) == "Start Link1 middle Link2 end"


def test_strip_markdown_links_url_with_parentheses():
    """Test URLs containing parentheses are correctly handled."""
    text = "[Wikipedia](https://en.wikipedia.org/wiki/Bracket_(disambiguation))"
    assert strip_markdown_links(text) == "Wikipedia"


def test_strip_markdown_links_url_with_nested_parens():
    """Test URLs with nested parentheses."""
    text = "[Link](https://example.com/foo_(bar)_baz)"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_inside_inline_code():
    """Test that links inside inline code are preserved."""
    text = "Use `[link](url)` syntax"
    assert strip_markdown_links(text) == "Use `[link](url)` syntax"


def test_strip_markdown_links_mixed_code_and_links():
    """Test mixing inline code and actual links."""
    text = "See [Doc](url) and use `[example](url)` format"
    assert strip_markdown_links(text) == "See Doc and use `[example](url)` format"


def test_strip_markdown_links_double_backtick_code():
    """Test that links inside double-backtick inline code are preserved."""
    text = "Use `` `[link](url)` `` syntax"
    assert strip_markdown_links(text) == "Use `` `[link](url)` `` syntax"


def test_strip_markdown_links_triple_backtick_code():
    """Test that links inside triple-backtick inline code are preserved."""
    text = "Use ``` ``[link](url)`` ``` syntax"
    assert strip_markdown_links(text) == "Use ``` ``[link](url)`` ``` syntax"


def test_strip_markdown_links_multi_backtick_mixed():
    """Test mixing multi-backtick code with real links."""
    text = "See [Real](url) but preserve `` `[code](url)` `` example"
    assert strip_markdown_links(text) == "See Real but preserve `` `[code](url)` `` example"


def test_strip_markdown_links_deeply_nested_parentheses():
    """Test URLs with deeply nested parentheses (2+ levels)."""
    text = "[Link](https://example.com/foo(bar(baz)))"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_triple_nested_parentheses():
    """Test URLs with triple-nested parentheses."""
    text = "[Link](https://example.com/foo(bar(baz(qux))))"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_nested_parens_with_text():
    """Test nested parentheses in URLs with surrounding text."""
    text = "See [Wikipedia](https://en.wikipedia.org/wiki/Foo(bar(baz))) for details"
    assert strip_markdown_links(text) == "See Wikipedia for details"


def test_strip_markdown_links_escaped_paren_in_url():
    """Test URLs with escaped parentheses."""
    text = r"[Link](https://example.com/foo\)bar)"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_escaped_paren_with_text():
    """Test escaped parentheses in URLs with surrounding text."""
    text = r"See [Link](https://example.com/foo\)bar) extra"
    assert strip_markdown_links(text) == "See Link extra"


def test_strip_markdown_links_escaped_bracket_in_link_text():
    """Test link text containing escaped brackets."""
    text = r"[Example [Label \]]](https://example.com)"
    assert strip_markdown_links(text) == r"Example [Label \]]"


def test_strip_markdown_links_multiple_escaped_chars():
    """Test multiple escaped characters in both link text and URL."""
    text = r"[Text with \] bracket](https://example.com/path\)extra)"
    assert strip_markdown_links(text) == r"Text with \] bracket"


def test_strip_markdown_links_escaped_opening_bracket():
    """Test that escaped opening bracket is not treated as link start."""
    text = r"Escaped \[Link](https://example.com)"
    assert strip_markdown_links(text) == r"Escaped \[Link](https://example.com)"


def test_strip_markdown_links_escaped_backtick():
    """Test that escaped backticks are not treated as code delimiters."""
    text = r"Escaped \`[Link](url)\` text"
    assert strip_markdown_links(text) == r"Escaped \`Link\` text"


def test_strip_markdown_links_inline_image():
    """Test that inline images have the ! prefix removed."""
    text = "![Alt text](image.png)"
    assert strip_markdown_links(text) == "Alt text"


def test_strip_markdown_links_inline_image_with_text():
    """Test inline images with surrounding text."""
    text = "See ![Logo](logo.png) for details"
    assert strip_markdown_links(text) == "See Logo for details"


def test_strip_markdown_links_mixed_links_and_images():
    """Test mixing regular links and inline images."""
    text = "[Link](url) and ![Image](img.png) example"
    assert strip_markdown_links(text) == "Link and Image example"


def test_strip_markdown_links_escaped_image_marker():
    """Test that escaped image marker is preserved (not treated as image)."""
    text = r"\![Alt](logo.png) heading"
    assert strip_markdown_links(text) == r"\![Alt](logo.png) heading"


def test_strip_markdown_links_escaped_image_with_real_link():
    """Test escaped image marker mixed with real link."""
    text = r"See \![Logo](logo.png) and [Real](url) here"
    assert strip_markdown_links(text) == r"See \![Logo](logo.png) and Real here"


def test_strip_markdown_links_angle_bracketed_url():
    """Test angle-bracketed URL is handled correctly."""
    text = "[Link](<foo(bar>)"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_angle_bracketed_url_with_parens():
    """Test angle-bracketed URL containing parentheses."""
    text = "[Link](<url(with)parens>)"
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_angle_bracketed_url_with_text():
    """Test angle-bracketed URL with surrounding text."""
    text = "See [Wikipedia](<https://en.wikipedia.org/wiki/Foo(bar)>) for info"
    assert strip_markdown_links(text) == "See Wikipedia for info"


def test_strip_markdown_links_reference_style_link():
    """Test reference-style link is stripped correctly."""
    text = "[Docs][ref] heading"
    assert strip_markdown_links(text) == "Docs heading"


def test_strip_markdown_links_reference_style_image():
    """Test reference-style image is stripped correctly."""
    text = "![Logo][badge] header"
    assert strip_markdown_links(text) == "Logo header"


def test_strip_markdown_links_reference_style_shortcut():
    """Test reference-style shortcut link [text][]."""
    text = "[ref][] description"
    assert strip_markdown_links(text) == "ref description"


def test_strip_markdown_links_multiple_reference_links():
    """Test multiple reference-style links."""
    text = "[First][ref1] and [Second][ref2] text"
    assert strip_markdown_links(text) == "First and Second text"


def test_strip_markdown_links_mixed_inline_and_reference():
    """Test mixing inline and reference-style links."""
    text = "[Inline](url) and [Reference][ref] links"
    assert strip_markdown_links(text) == "Inline and Reference links"


def test_find_inline_code_spans_unmatched_backticks():
    """Test that unmatched backticks don't create spans."""
    from toc_markdown.parser import find_inline_code_spans

    # Single backtick without closing
    assert find_inline_code_spans("`code") == []
    # Different number of opening and closing backticks
    assert find_inline_code_spans("``code`") == []
    # No backticks at all
    assert find_inline_code_spans("no code") == []


def test_find_inline_code_spans_escaped_backticks():
    """Test that escaped backticks are not treated as delimiters."""
    from toc_markdown.parser import find_inline_code_spans

    # Escaped backtick should not start a code span
    # In the string "\\`not code\\`", the backslash escapes the backtick
    assert find_inline_code_spans("\\`not code\\`") == []
    # Mixed: first backtick is escaped (\\`), the unescaped backtick at position 10
    # starts a code span that ends at position 17 (the next backtick)
    assert find_inline_code_spans("\\`not code` but `this` is") == [(10, 17)]


def test_strip_markdown_links_angle_bracket_no_close():
    """Test angle-bracketed URL without closing angle bracket."""
    text = "[Link](<url)"
    # Should not be treated as valid link since > is missing
    assert strip_markdown_links(text) == "[Link](<url)"


def test_strip_markdown_links_angle_bracket_no_close_paren():
    """Test angle-bracketed URL without closing parenthesis."""
    text = "[Link](<url>"
    # Should not be treated as valid link since ) is missing
    assert strip_markdown_links(text) == "[Link](<url>"


def test_strip_markdown_links_unbalanced_brackets():
    """Test unbalanced brackets are not treated as links."""
    # This tests the case where we have nested brackets that ARE balanced
    # The parser handles nested brackets by counting depth
    text = "[Link[text]](url)"
    # Nested brackets with proper closing
    result = strip_markdown_links(text)
    assert result == "Link[text]"


def test_strip_markdown_links_incomplete_reference():
    """Test incomplete reference-style link."""
    text = "[Link][ref"
    # Missing closing bracket for reference
    assert strip_markdown_links(text) == "[Link][ref"


def test_strip_markdown_links_empty_result_stack():
    """Test image handling when result stack is empty."""
    text = "![Alt](url)"
    # This tests the edge case where result[-1] would fail if empty
    assert strip_markdown_links(text) == "Alt"


def test_strip_markdown_links_bracket_at_start():
    """Test bracket at start of string."""
    text = "[Link](url) text"
    # Tests the i > 0 check for image detection
    assert strip_markdown_links(text) == "Link text"


def test_strip_markdown_links_escaped_bracket_in_code():
    """Test escaped bracket inside inline code."""
    text = r"Use `\[code]` syntax"
    # Code should be preserved, including escaped bracket
    assert strip_markdown_links(text) == r"Use `\[code]` syntax"


def test_strip_markdown_links_no_url_after_bracket():
    """Test bracket followed by neither ( nor [."""
    text = "[Link] not a link"
    # ] not followed by ( or [ means it's not a link
    assert strip_markdown_links(text) == "[Link] not a link"


def test_strip_markdown_links_angle_bracket_with_whitespace_only():
    """Test angle-bracketed URL with only whitespace after >."""
    text = "[Link](<url>   )"
    # Whitespace between > and ) should be skipped
    assert strip_markdown_links(text) == "Link"


def test_strip_markdown_links_multiple_escaped_in_ref():
    """Test multiple escaped characters in reference-style link."""
    text = r"[Text][ref\]escaped]"
    # The \] should be skipped and we look for next ]
    result = strip_markdown_links(text)
    # Should find the link and strip it
    assert result == "Text"


def test_strip_markdown_links_nested_brackets_complex():
    """Test complex nested brackets in link text."""
    text = "[[Nested]](url)"
    # Should handle nested brackets
    assert strip_markdown_links(text) == "[Nested]"
