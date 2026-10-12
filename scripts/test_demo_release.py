import tempfile
import unittest
from pathlib import Path
from check_outreach_navigation_release import check_demo

class DemoReleaseTests(unittest.TestCase):
    def bundle(self, root, page):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        dist = Path(directory.name)
        (dist / 'assets').mkdir()
        (dist / 'index.html').write_text('<script src="/assets/index-active.js"></script>')
        (dist / 'assets/index-active.js').write_text(root)
        (dist / 'assets/DemoAgentsPage-active.js').write_text(page)
        return dist

    def test_accepts_current_safe_demo(self):
        check_demo(self.bundle('/demo/room demo-coat-care Подтвердить проверку в демо reviewTexts reviewTitle', 'unused'))

    def test_rejects_old_demo_entry(self):
        with self.assertRaisesRegex(ValueError, 'Outdated demo'):
            check_demo(self.bundle('old entry', 'textarea Подтвердить проверку в демо'))

    def test_unused_new_page_cannot_hide_old_active_page(self):
        dist = self.bundle('/demo/room demo-coat-care DemoAgentsPage-active.js', 'approve unseen replies')
        (dist / 'assets/DemoAgentsPage-unused.js').write_text('textarea Подтвердить проверку в демо')
        with self.assertRaisesRegex(ValueError, 'Outdated demo'):
            check_demo(dist)

if __name__ == '__main__':
    unittest.main()
