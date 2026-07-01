import sys


def test_partnership_lead_routes_stay_registered_after_block_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
    }

    expected = {
        ("/api/partnership/leads", frozenset({"GET"}), "partnership_leads_api.partnership_list_leads"),
        (
            "/api/partnership/leads/<string:lead_id>",
            frozenset({"PATCH"}),
            "partnership_leads_api.partnership_update_lead",
        ),
        (
            "/api/partnership/leads/<string:lead_id>",
            frozenset({"DELETE"}),
            "partnership_leads_api.partnership_delete_lead",
        ),
        (
            "/api/partnership/leads/bulk-update",
            frozenset({"POST"}),
            "partnership_leads_api.partnership_bulk_update_leads",
        ),
        (
            "/api/partnership/leads/bulk-delete",
            frozenset({"POST"}),
            "partnership_leads_api.partnership_bulk_delete_leads",
        ),
        (
            "/api/partnership/leads/<string:lead_id>/manual-contact",
            frozenset({"POST"}),
            "partnership_leads_api.partnership_mark_lead_manual_contact",
        ),
        (
            "/api/partnership/leads/<string:lead_id>/prepare-room",
            frozenset({"POST"}),
            "partnership_leads_api.partnership_prepare_sales_room",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/status",
            frozenset({"POST"}),
            "partnership_leads_api.update_lead_status",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/manual-contact",
            frozenset({"POST"}),
            "partnership_leads_api.mark_lead_manual_contact",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/comment",
            frozenset({"POST"}),
            "partnership_leads_api.add_lead_comment",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/timeline",
            frozenset({"GET"}),
            "partnership_leads_api.get_lead_timeline",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/shortlist",
            frozenset({"POST"}),
            "partnership_leads_api.review_lead_shortlist",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/select",
            frozenset({"POST"}),
            "partnership_leads_api.select_lead_for_outreach",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/channel",
            frozenset({"POST"}),
            "partnership_leads_api.select_outreach_channel",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/contacts",
            frozenset({"POST"}),
            "partnership_leads_api.update_lead_contacts",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>/language",
            frozenset({"POST"}),
            "partnership_leads_api.update_lead_language",
        ),
        (
            "/api/admin/prospecting/lead/<string:lead_id>",
            frozenset({"DELETE"}),
            "partnership_leads_api.delete_lead",
        ),
    }

    assert expected.issubset(routes)
