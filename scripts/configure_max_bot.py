#!/usr/bin/env python3
"""Read-only by default. --apply registers the configured MAX bot webhook/menu."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from services.max_transport import MaxTransport, MaxTransportError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not os.getenv('MAX_BOT_TOKEN'):
        parser.error('MAX_BOT_TOKEN must be loaded from the protected deployment environment')
    transport = MaxTransport()
    try:
        bot = transport.call('GET', '/me')
        if not bot.get('is_bot'):
            parser.error('MAX did not identify a bot')
        print('Bot identity verified')
        subscriptions = transport.call('GET', '/subscriptions')
        print('Webhook subscriptions:', len(subscriptions.get('subscriptions') or []))
        if not args.apply:
            print('Read-only check complete; no settings changed')
            return
        secret = os.getenv('MAX_WEBHOOK_SECRET', '')
        if len(secret) < 32:
            parser.error('Set MAX_WEBHOOK_SECRET to a random value of at least 32 characters')
        from services.mobile_bot_menu import max_command_menu
        transport.call('PATCH', '/me', body={'commands': max_command_menu()})
        transport.call('POST', '/subscriptions', body={'url': 'https://localos.pro/api/max/webhook',
            'update_types': ['message_created', 'message_callback', 'bot_started', 'bot_stopped', 'bot_added', 'bot_removed'],
            'secret': secret})
        print('Webhook/menu configuration accepted; verify a real private conversation before rollout')
    except MaxTransportError:
        error = sys.exception()
        print('MAX configuration failed:', error.code, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
