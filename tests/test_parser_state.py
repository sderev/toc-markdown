from toc_markdown.models import ParserContext, ParserState
from toc_markdown.parser import (
    _try_close_fence,
    _try_enter_indented_code,
    _try_exit_indented_code,
    _try_open_fence,
    _try_enter_toc,
    _try_exit_toc,
)


def test_try_open_fence_sets_context_fields():
    ctx = ParserContext()

    opened = _try_open_fence(ctx, "   ```python\n")

    assert opened is True
    assert ctx.state is ParserState.IN_FENCED_CODE
    assert ctx.fence_char == "`"
    assert ctx.fence_length == 3
    assert ctx.fence_indent_columns == 3


def test_try_open_fence_ignored_when_already_in_code():
    ctx = ParserContext(state=ParserState.IN_FENCED_CODE, fence_char="~", fence_length=3)

    assert _try_open_fence(ctx, "```") is False
    assert ctx.fence_char == "~"
    assert ctx.fence_length == 3


def test_try_close_fence_respects_indent_limit():
    ctx = ParserContext(
        state=ParserState.IN_FENCED_CODE,
        fence_char="`",
        fence_length=3,
        fence_indent_columns=0,
    )

    assert _try_close_fence(ctx, "    ```\n") is False

    assert _try_close_fence(ctx, "```") is True
    assert ctx.state is ParserState.NORMAL
    assert ctx.fence_char is None
    assert ctx.fence_length == 0
    assert ctx.fence_indent_columns == 0


def test_try_close_fence_rejects_closer_with_excess_absolute_indent():
    ctx = ParserContext(
        state=ParserState.IN_FENCED_CODE,
        fence_char="`",
        fence_length=3,
        fence_indent_columns=3,
    )

    assert _try_close_fence(ctx, "      ```\n") is False
    assert ctx.state is ParserState.IN_FENCED_CODE


def test_try_enter_indented_code_switches_state():
    ctx = ParserContext()

    assert _try_enter_indented_code(ctx, "   text") is False
    assert _try_enter_indented_code(ctx, "    code block") is True
    assert ctx.state is ParserState.IN_INDENTED_CODE


def test_try_exit_indented_code_handles_transitions():
    ctx = ParserContext(state=ParserState.IN_INDENTED_CODE)

    assert _try_exit_indented_code(ctx, "    still indented") is True
    assert ctx.state is ParserState.IN_INDENTED_CODE

    assert _try_exit_indented_code(ctx, "\n") is True
    assert ctx.state is ParserState.IN_INDENTED_CODE

    assert _try_exit_indented_code(ctx, "no longer indented") is False
    assert ctx.state is ParserState.NORMAL


def test_try_enter_toc_pushes_end_line():
    ctx = ParserContext()
    toc_end_stack: list[int] = []
    toc_start_to_end = {3: 7}

    assert _try_enter_toc(ctx, 1, toc_start_to_end, toc_end_stack) is False
    assert ctx.state is ParserState.NORMAL
    assert toc_end_stack == []

    assert _try_enter_toc(ctx, 3, toc_start_to_end, toc_end_stack) is True
    assert ctx.state is ParserState.IN_TOC
    assert toc_end_stack == [7]


def test_try_exit_toc_resets_state_after_matching_end():
    ctx = ParserContext(state=ParserState.IN_TOC)
    toc_end_stack = [8, 5]

    assert _try_exit_toc(ctx, 4, toc_end_stack) is False
    assert ctx.state is ParserState.IN_TOC
    assert toc_end_stack == [8, 5]

    assert _try_exit_toc(ctx, 5, toc_end_stack) is True
    assert ctx.state is ParserState.IN_TOC
    assert toc_end_stack == [8]

    assert _try_exit_toc(ctx, 8, toc_end_stack) is True
    assert ctx.state is ParserState.NORMAL
    assert toc_end_stack == []
