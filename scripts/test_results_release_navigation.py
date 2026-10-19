import tempfile
import unittest
from pathlib import Path
from check_outreach_navigation_release import check

class ResultsReleaseNavigationTests(unittest.TestCase):
    def bundle(self, label):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        dist = Path(directory.name)
        (dist / 'assets').mkdir()
        (dist / 'index.html').write_text('<script src="/assets/index-active.js"></script>')
        (dist / 'assets/index-active.js').write_text('OperatorPage-active.js PartnershipSearchPage-active.js DashboardLayout-active.js /demo/room demo-coat-care Подтвердить проверку в демо reviewTexts reviewTitle')
        (dist / 'assets/OperatorPage-active.js').write_text('Меню Оператора Текущая задача: К последним сообщениям outreach_result_event_id')
        (dist / 'assets/PartnershipSearchPage-active.js').write_text('Этапы аутрича Компании Письма search_task_id "brand"')
        (dist / 'assets/DashboardLayout-active.js').write_text('/dashboard/operator /dashboard/partnerships /dashboard/influencers /dashboard/agents Автоматизация ' + label)
        return dist

    def test_accepts_current_chat_name(self):
        check(self.bundle('Чат с LocalOS'))

    def test_keeps_legacy_chat_name_compatible(self):
        check(self.bundle('Управление через чат'))

    def test_rejects_missing_direct_chat_entry(self):
        with self.assertRaisesRegex(ValueError, 'Outdated sidebar'):
            check(self.bundle('unrelated text'))

if __name__ == '__main__':
    unittest.main()
