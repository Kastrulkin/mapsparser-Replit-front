"""Negative controls for the synthetic restore data comparator; no DB/network."""

import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).with_name('synthetic_restore_hflypi.py')
spec = importlib.util.spec_from_file_location('hflypi_restore_check', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RestoreComparatorChecks(unittest.TestCase):
    def setUp(self):
        self.source = {
            'objects': '[["public", "probe", "r"]]',
            'rows': 'probe|{"payload":null,"value":1}\nprobe|{"payload":null,"value":1}',
            'sequences': 'probe_id_seq|2|true',
        }

    def test_identical_complete_multisets_pass(self):
        module.compare_logical_data(self.source, dict(self.source))

    def test_each_semantic_change_is_rejected(self):
        variants = [
            ('rows', self.source['rows'].splitlines()[0]),
            ('rows', self.source['rows'] + '\n' + self.source['rows'].splitlines()[0]),
            ('rows', self.source['rows'].replace('null', '""')),
            ('rows', self.source['rows'].replace(':1', ':"1"')),
            ('sequences', 'probe_id_seq|1|true'),
            ('sequences', 'probe_id_seq|2|false'),
            ('objects', '[]'),
        ]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                target = dict(self.source)
                target[key] = value
                with self.assertRaises(module.VerificationError):
                    module.compare_logical_data(self.source, target)


if __name__ == '__main__':
    unittest.main()
