import inspect
import sys


if "src" not in sys.path:
    sys.path.insert(0, "src")

from database_manager import DatabaseManager
from services.partnership_leads_service import partnership_list_leads


class CapturingCursor:
    def __init__(self):
        self.queries = []
        self.description = []

    def execute(self, query, params=None):
        self.queries.append((str(query), params))

    def fetchall(self):
        return []


class CapturingConnection:
    def __init__(self):
        self.cursor_instance = CapturingCursor()

    def cursor(self):
        return self.cursor_instance


def _manager_with_parser_scope():
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = CapturingConnection()
    manager.db_type = "postgresql"
    manager._businesses_has_column = lambda _column: False
    manager._prospectingleads_support_parser_scope = lambda: True
    return manager


def test_superadmin_business_list_excludes_lead_parser_businesses():
    manager = _manager_with_parser_scope()

    manager.get_all_businesses()

    query = manager.conn.cursor_instance.queries[-1][0]
    assert "NOT EXISTS" in query
    assert "parser_lead.parse_business_id = b.id" in query
    assert "parser_lead.business_id <> b.id" in query


def test_owner_business_lists_exclude_lead_parser_businesses():
    manager = _manager_with_parser_scope()
    manager.get_businesses_by_owner("owner-1")
    direct_query = manager.conn.cursor_instance.queries[-1][0]

    manager.get_businesses_by_network_owner("owner-1")
    network_queries = [query for query, _params in manager.conn.cursor_instance.queries[-2:]]

    assert "NOT EXISTS" in direct_query
    assert all("NOT EXISTS" in query for query in network_queries)


def test_partnership_leads_expose_the_client_business_label():
    source = inspect.getsource(partnership_list_leads)

    assert "AS client_business_name" in source
    assert "client_business.id = prospectingleads.business_id" in source


def test_partnership_leads_expose_persisted_audit_and_match_summary():
    source = inspect.getsource(partnership_list_leads)

    assert "AS audit_ready" in source
    assert "AS match_summary_json" in source
    assert "partnershipleadartifacts artifact" in source
