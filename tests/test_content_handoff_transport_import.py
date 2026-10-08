"""The handoff must use the service facade that binds transport dependencies."""

import ast
from pathlib import Path


def test_handoff_imports_photo_transport_from_canonical_facade():
    source = Path('src/services/agent_capability_handlers.py').read_text()
    tree = ast.parse(source)
    handler = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == '_handle_content_publish_handoff')
    photo_imports = [node.module for node in ast.walk(handler)
                    if isinstance(node, ast.ImportFrom)
                    and any(alias.name == 'send_telegram_photo_message'
                            for alias in node.names)]
    assert photo_imports == ['services.social_post_service']


def test_canonical_photo_transport_is_available():
    from services.social_post_service import send_telegram_photo_message

    assert callable(send_telegram_photo_message)
