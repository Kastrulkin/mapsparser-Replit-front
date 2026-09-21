"""Pure cache dependency-order controls; no Docker call or mutation."""

import json
from pathlib import Path
import runpy


SUPPORT = Path(__file__).resolve().parent


def main():
    order = runpy.run_path(str(SUPPORT / 'cache_buildkit_leaf_cleanup_hflypi.py'))['leaf_first']
    rows = [{'ID': 'base', 'Parents': []}, {'ID': 'child', 'Parents': ['base']}]
    assert order(rows, ['base', 'child']) == ['child', 'base']
    for inventory, targets in [
        (rows, ['base']),
        (rows, ['missing']),
        (rows, ['base', 'base']),
        (rows + [rows[0]], ['base', 'child']),
        ([{'ID': 'a', 'Parents': ['b']}, {'ID': 'b', 'Parents': ['a']}], ['a', 'b']),
    ]:
        denied = False
        try:
            order(inventory, targets)
        except RuntimeError:
            denied = True
        assert denied
    proof = json.loads((SUPPORT.parent / 'evidence/old-audit-buildkit-cleanup-20260921.json').read_text())
    pending = [target for target in proof['targets'] if target not in proof['removed_cache_ids']]
    actual = order(proof['remaining_inventory'], pending)
    assert len(actual) == len(set(actual)) == 18
    assert set(actual) == set(pending)
    positions = {target: index for index, target in enumerate(actual)}
    for row in proof['remaining_inventory']:
        for parent in row.get('Parents') or []:
            if parent in positions:
                assert row['ID'] in positions
                assert positions[row['ID']] < positions[parent]
    print('child-before-parent, five denial cases and exact live18 graph passed')


if __name__ == '__main__':
    main()
