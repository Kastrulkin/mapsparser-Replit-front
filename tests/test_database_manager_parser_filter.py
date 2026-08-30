from database_manager import DatabaseManager


def test_lead_parser_filter_compares_uuid_reference_with_text_business_id():
    manager = DatabaseManager.__new__(DatabaseManager)
    manager._prospectingleads_support_parser_scope = lambda: True

    filter_sql = manager._lead_parser_business_filter("b.id")

    assert "CONCAT(parser_lead.parse_business_id) = b.id" in filter_sql
