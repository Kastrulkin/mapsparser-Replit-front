import tempfile
import unittest
from pathlib import Path
from check_outreach_navigation_release import check_operator

class OperatorReleaseTests(unittest.TestCase):
    def bundle(self, page, extra=''):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'assets').mkdir()
        (root / 'index.html').write_text('<script src="/assets/index-active.js"></script>')
        (root / 'assets/index-active.js').write_text('"OperatorPage-active.js"')
        (root / 'assets/OperatorPage-active.js').write_text(page)
        (root / 'assets/OperatorPage-unused.js').write_text(extra)
        return root

    def test_current_operator_accepts_dependency_markers(self):
        root = self.bundle('Меню Оператора Текущая задача: ./chat.js')
        (root / 'assets/chat.js').write_text('К последним сообщениям outreach_result_event_id')
        check_operator(root)

    def test_unused_new_bundle_cannot_hide_active_old_page(self):
        root = self.bundle('old page', 'Меню Оператора Текущая задача: К последним сообщениям outreach_result_event_id')
        with self.assertRaisesRegex(ValueError, 'Outdated Operator'):
            check_operator(root)

    def test_missing_active_dependency_fails_release(self):
        root = self.bundle('Меню Оператора ./missing.js')
        with self.assertRaises(OSError):
            check_operator(root)

if __name__ == '__main__':
    unittest.main()
