"""
Compatibility shim for legacy imports.

Historically, API routes lived in chatgpt_api.py and exposed `chatgpt_bp`.
The module was renamed to messengers_api.py with blueprint `messengers_bp`.
Some runtime entrypoints still import `chatgpt_bp`, so keep this adapter.
"""

from messengers_api import messengers_bp as chatgpt_bp

