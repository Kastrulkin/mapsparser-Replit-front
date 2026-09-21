"""Resume the remaining18 approved IDs after the recorded three-leaf removal."""

import argparse
from pathlib import Path
import runpy


TARGETS = (
    't4odgqqt0xeps3h2n8c5w69mz', 'kcy33m9st5459ttbz6ow8andt',
    'ucczsnjw73pr2ack4ct33m853', 'ic6n1ksrq546vug9fi1bil2or',
    'kd4ap9fob76t2946lohxiolho', 'ph6ye1kycmoprzf3q9tjaahap',
    'zamye543v75atoz3uq4uvvvw3', '1s3n4589xyh4tmd8npr60413v',
    '1qvg8om50rls6e4jcpcza6r95', 'o7dlg7lpqcnbtnjuf6f4f6vno',
    '4n3k2msdbnbmii6v6t2tdotzk', 'g0y740jzofpd3o9wz0wosm2j9',
    'zutjbdsta15z9wt9wlgwv6ddt', 'mlasqqre6gg40ub3mfmi4qlkx',
    '7bitboaeyifvhcn826l17cmvp', 'lup4z2wgm7u690r8v7s5qphgv',
    'x2hlsw6q4itzie569ap6ifkw2', 'koi63eq1e7a0pv0i9a15taqno',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    if not parser.parse_args().execute:
        parser.error('explicit --execute is required for the reviewed fixed allowlist')
    support = Path(__file__).resolve().parent
    helper = runpy.run_path(str(support / 'cache_buildkit_leaf_cleanup_hflypi.py'))
    helper['main'](targets=TARGETS, result_path=support.parent / 'evidence/old-audit-buildkit-cleanup-v2-20260921.json')


if __name__ == '__main__':
    main()
