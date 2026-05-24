from services.operator_services_optimization import (
    apply_service_optimization_suggestions,
    classify_services_optimize_intent,
    optimize_services_from_operator,
)


class FakeCursor:
    def __init__(self, *, balance=100, services=None):
        self.balance = balance
        self.services = services or [
            {
                "id": "svc-1",
                "name": "Массаж лица",
                "description": "Расслабляющий массаж",
                "optimized_name": "",
                "optimized_description": "",
                "category": "beauty",
                "price": "2500",
            },
            {
                "id": "svc-2",
                "name": "Коррекция бровей",
                "description": "Форма бровей",
                "optimized_name": "",
                "optimized_description": "",
                "category": "beauty",
                "price": "1200",
            },
        ]
        self.last_query = ""
        self.last_params = ()
        self.current_reservation_lookup = False
        self.reservation = None
        self.jobs = []
        self.items = []
        self.ledger_entries = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        self.current_reservation_lookup = "from operatorcreditreservations" in self.last_query and "where id =" in self.last_query
        if "insert into operatorcreditreservations" in self.last_query:
            self.reservation = {
                "id": params[0],
                "business_id": params[1],
                "user_id": params[2],
                "action_key": params[3],
                "status": "reserved",
                "reserved_credits": params[6],
                "charged_credits": 0,
                "released_credits": 0,
            }
        if "insert into serviceregenerationjobs" in self.last_query:
            self.jobs.append({"id": params[0], "status": "suggested", "selected_count": params[6]})
        if "insert into serviceregenerationjobitems" in self.last_query:
            self.items.append(
                {
                    "id": params[0],
                    "job_id": params[1],
                    "service_id": params[2],
                    "status": "suggested",
                    "before_optimized_name": params[4],
                    "before_optimized_description": params[5],
                    "after_optimized_name": params[6],
                    "after_optimized_description": params[7],
                }
            )
        if "update userservices set optimized_name" in self.last_query:
            for service in self.services:
                if service["id"] == params[2]:
                    service["optimized_name"] = params[0]
                    service["optimized_description"] = params[1]
        if "update serviceregenerationjobitems set status = 'fixed'" in self.last_query:
            for item in self.items:
                if item["id"] == params[0] and item["job_id"] == params[1]:
                    item["status"] = "fixed"
        if "update serviceregenerationjobs set status" in self.last_query:
            for job in self.jobs:
                if job["id"] == params[7]:
                    job["status"] = params[0]
                    job["selected_count"] = params[1]
                    job["fixed_count"] = params[2]
                    job["failed_count"] = params[3]
                    job["manual_review_count"] = params[4]
                    job["message"] = params[5]
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query and self.reservation:
            self.reservation["status"] = params[0]
            self.reservation["charged_credits"] = params[1]
            self.reservation["released_credits"] = params[2]

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            return {"to_regclass": str(params[0]).replace("public.", "")}
        if "from operatorconsentpolicies" in query:
            return {"mode": "ask_each_time"}
        if "select credits_balance from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0, "used_credits": 0}
        if self.current_reservation_lookup:
            return self.reservation
        if "returning id, status, reserved_credits" in query:
            return {"id": self.reservation["id"], "status": "reserved", "reserved_credits": self.reservation["reserved_credits"]}
        if "returning id, status, selected_count" in query:
            return self.jobs[-1] if self.jobs else None
        if "returning id, service_id, status" in query:
            return self.items[-1] if self.items else None
        if "from serviceregenerationjobs" in query and "where id =" in query:
            for job in self.jobs:
                if job["id"] == params[0]:
                    return job
            return None
        if "count(*) filter" in query:
            matching = [item for item in self.items if item["job_id"] == params[0]]
            return {
                "fixed_count": len([item for item in matching if item["status"] == "fixed"]),
                "suggested_count": len([item for item in matching if item["status"] == "suggested"]),
                "failed_count": len([item for item in matching if item["status"] == "failed"]),
                "manual_review_count": len([item for item in matching if item["status"] in ("manual_review", "manual_review_skipped")]),
                "selected_count": len(matching),
            }
        if "returning id, status, selected_count, fixed_count" in query:
            for job in self.jobs:
                if job["id"] == params[7]:
                    return job
            return None
        return None

    def fetchall(self):
        if "from serviceregenerationjobitems" in self.last_query and "join userservices" in self.last_query:
            job_id = self.last_params[0]
            business_id = self.last_params[1]
            limit = self.last_params[-1]
            item_ids = []
            if len(self.last_params) == 4:
                item_ids = self.last_params[2]
            rows = []
            for item in self.items:
                if item["job_id"] != job_id or item["status"] != "suggested":
                    continue
                if item_ids and item["id"] not in item_ids:
                    continue
                service = next((service for service in self.services if service["id"] == item["service_id"]), None)
                if not service or service.get("business_id", business_id) != business_id:
                    continue
                rows.append({**service, **item})
            return rows[:limit]
        if "from userservices" in self.last_query:
            return self.services
        return []


def fake_services_generator(prompt, *, business_id, user_id):
    return (
        '{"services": ['
        '{"service_id": "svc-1", "optimized_name": "Массаж лица с уходом", "seo_description": "Расслабляющий массаж лица с рекомендациями по уходу."},'
        '{"service_id": "svc-2", "optimized_name": "Коррекция бровей у мастера", "seo_description": "Аккуратная коррекция формы бровей для естественного результата."}'
        ']}'
    )


def failing_services_generator(prompt, *, business_id, user_id):
    raise RuntimeError("model unavailable")


def test_classifies_services_optimize_intent() -> None:
    assert classify_services_optimize_intent("Оптимизируй услуги")
    assert classify_services_optimize_intent("Улучши SEO описания услуг")
    assert not classify_services_optimize_intent("Подготовь пост для соцсетей")


def test_optimize_services_saves_suggestions_and_charges() -> None:
    cursor = FakeCursor(balance=100)

    result = optimize_services_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        services_generator=fake_services_generator,
    )

    assert result["status"] == "completed"
    assert result["intent"] == "services_optimize"
    assert result["charged_credits"] == 2
    assert result["credit_charged"] is True
    assert result["manual_apply_required"] is True
    assert result["external_writes_performed"] is False
    assert len(cursor.items) == 2
    assert cursor.items[0]["after_optimized_name"] == "Массаж лица с уходом"
    assert cursor.ledger_entries[0][2] == -2


def test_optimize_services_blocks_without_credits() -> None:
    cursor = FakeCursor(balance=1)

    result = optimize_services_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        services_generator=fake_services_generator,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert len(cursor.items) == 0
    assert len(cursor.ledger_entries) == 0


def test_optimize_services_releases_when_generation_fails() -> None:
    cursor = FakeCursor(balance=100)

    result = optimize_services_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        services_generator=failing_services_generator,
    )

    assert result["status"] == "blocked"
    assert result["finalization_result"]["status"] == "released"
    assert len(cursor.items) == 0
    assert len(cursor.ledger_entries) == 0


def test_apply_service_optimization_suggestions_updates_userservices_after_confirmation() -> None:
    cursor = FakeCursor(balance=100)
    optimize_result = optimize_services_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        services_generator=fake_services_generator,
    )

    result = apply_service_optimization_suggestions(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        job_id=optimize_result["optimization_job"]["id"],
        limit=5,
        explicit_confirmation=True,
    )

    assert result["status"] == "completed"
    assert result["intent"] == "services_optimize_apply"
    assert result["applied_count"] == 2
    assert result["external_writes_performed"] is False
    assert result["credit_charged"] is False
    assert cursor.services[0]["optimized_name"] == "Массаж лица с уходом"
    assert cursor.services[1]["optimized_description"] == "Аккуратная коррекция формы бровей для естественного результата."
    assert all(item["status"] == "fixed" for item in cursor.items)


def test_apply_service_optimization_requires_explicit_confirmation() -> None:
    cursor = FakeCursor(balance=100)
    optimize_result = optimize_services_from_operator(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        services_generator=fake_services_generator,
    )

    result = apply_service_optimization_suggestions(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        job_id=optimize_result["optimization_job"]["id"],
        limit=5,
    )

    assert result["status"] == "blocked"
    assert "explicit_confirmation_required" in result["blocked_reasons"]
    assert result["manual_approval_received"] is False
    assert cursor.services[0]["optimized_name"] == ""
    assert cursor.services[0]["optimized_description"] == ""
    assert all(item["status"] == "suggested" for item in cursor.items)


def test_apply_service_optimization_blocks_unknown_job() -> None:
    cursor = FakeCursor(balance=100)

    result = apply_service_optimization_suggestions(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        job_id="missing-job",
        explicit_confirmation=True,
    )

    assert result["status"] == "blocked"
    assert "service_suggestion_job_not_found" in result["blocked_reasons"]
