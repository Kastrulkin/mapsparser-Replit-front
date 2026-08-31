from core.html_head import replace_or_insert_tag


def test_canonical_replacement_treats_backslashes_as_literal_text():
    html = '<html><head><link rel="canonical" href="https://localos.pro/" /></head></html>'

    rendered = replace_or_insert_tag(
        html,
        r'<link\s+rel="canonical"[^>]*>',
        '<link rel="canonical" href="https://localos.pro/foo\\windows" />',
    )

    assert 'href="https://localos.pro/foo\\windows"' in rendered
