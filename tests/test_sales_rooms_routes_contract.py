import sys


def test_public_sales_room_routes_stay_registered_after_blueprint_split():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    import main

    routes = {
        (str(rule), frozenset(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint)
        for rule in main.app.url_map.iter_rules()
    }

    expected = {
        ("/api/sales-rooms/public/<string:slug>", frozenset({"GET"}), "sales_rooms_api.public_sales_room"),
        (
            "/api/sales-rooms/public/<string:slug>/welcome",
            frozenset({"PATCH"}),
            "sales_rooms_api.public_sales_room_welcome",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/proposal/suggestions",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_proposal_suggestion",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/proposal/suggestions/<string:suggestion_id>/resolve",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_proposal_suggestion_resolve",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/messages",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_message",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/files",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_file_upload",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/files/<string:file_id>",
            frozenset({"GET"}),
            "sales_rooms_api.public_sales_room_file",
        ),
        (
            "/api/sales-rooms/public/<string:slug>/events",
            frozenset({"POST"}),
            "sales_rooms_api.public_sales_room_event",
        ),
    }

    assert expected.issubset(routes)
