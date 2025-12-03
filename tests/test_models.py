from toc_markdown.models import ParserContext, ParserState


def test_parser_state_members():
    assert list(ParserState) == [
        ParserState.NORMAL,
        ParserState.IN_FENCED_CODE,
        ParserState.IN_INDENTED_CODE,
    ]


def test_parser_context_defaults():
    ctx = ParserContext()

    assert ctx.state is ParserState.NORMAL
    assert ctx.fence_char is None
    assert ctx.fence_length == 0
    assert ctx.fence_indent_columns == 0


def test_parser_context_custom_values():
    ctx = ParserContext(
        state=ParserState.IN_FENCED_CODE,
        fence_char="`",
        fence_length=3,
        fence_indent_columns=2,
    )

    assert ctx.state is ParserState.IN_FENCED_CODE
    assert ctx.fence_char == "`"
    assert ctx.fence_length == 3
    assert ctx.fence_indent_columns == 2
