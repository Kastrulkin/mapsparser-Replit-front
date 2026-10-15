#!/usr/bin/env python3
"""Rebuild the source inventory; importing Telegram must never start a bot."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def value(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return ast.unparse(node)


def inventory():
    rows = []
    for source_path in ['src/telegram_bot.py', 'src/services/owner_finance_input.py', 'src/services/operator_telegram_voice.py']:
        source = ROOT / source_path
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name == 'CommandHandler' and len(node.args) >= 2:
                rows.append({'kind': 'command', 'value': value(node.args[0]), 'handler': ast.unparse(node.args[1]), 'source': source_path, 'line': node.lineno})
            if name == 'InlineKeyboardButton':
                options = {item.arg: value(item.value) for item in node.keywords if item.arg}
                rows.append({'kind': 'button', 'label': value(node.args[0]) if node.args else options.get('text'),
                             **options, 'source': source_path, 'line': node.lineno})
        for node in tree.body:
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Compare) and isinstance(child.left, ast.Name) and child.left.id == 'data':
                        rows.append({'kind': 'callback_branch', 'value': [value(item) for item in child.comparators],
                                     'handler': node.name, 'source': source_path, 'line': child.lineno})
        for node in tree.body:
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name) and child.func.value.id == 'data' and child.func.attr in {'startswith', 'endswith'}:
                        rows.append({'kind': 'callback_pattern', 'value': [value(item) for item in child.args],
                            'match': child.func.attr, 'handler': node.name, 'source': source_path, 'line': child.lineno})
    mobile = ast.parse((ROOT / 'src/api/operator_api.py').read_text())
    for node in mobile.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_mobile_navigation':
            for child in ast.walk(node):
                if isinstance(child, ast.Dict):
                    fields = {value(k): value(v) for k, v in zip(child.keys, child.values) if k}
                    if 'key' in fields and 'label' in fields:
                        rows.append({'kind': 'screen', **fields, 'source': 'src/api/operator_api.py', 'line': child.lineno})
    for item in rows:
        item['acceptance_status'] = 'requires_paired_live_acceptance'
        item['authorization'] = {'source': item['source'] + ':' + str(item['line']), 'rule': 'current handler business/tenant permission checks; paired denied-access test required'}
        item['tariff'] = 'current capability_access_payload / subscription gate of this handler; paired closed-capability test required'
        item['expected_result'] = 'same business action, result, approval boundary and error as the referenced Telegram branch'
        item['acceptance_test'] = 'execute this exact entry on Telegram and MAX under the same account and scope; compare result, then repeat denied-access, expired-state and duplicate-click cases'
    return rows


if __name__ == '__main__':
    result = inventory()
    destination = ROOT / 'docs/MAX_TELEGRAM_SOURCE_INVENTORY.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Inventory:', len(result), 'source entries ->', destination.relative_to(ROOT))
