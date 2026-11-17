"""Provision only an explicitly reviewed tenant/actor binding. Dry-run by default.

PYTHONPATH=src python scripts/provision_inbound_case_pilot.py --config /secure/binding.json
Add --apply --key-file /secure/riderra-case.key after reviewing the dry-run.
The key file is exclusive-create, 0600; secrets never go to stdout.
No environment flags, membership grants, mail or model execution are changed.
"""
import argparse
import json
import os
import uuid

from pg_db_utils import get_db_connection
from core.agent_api_security import create_agent_client
from services.business_permissions import load_actor, require_permission
from services.inbound_case_contract import CONTRACT, STEPS, validate_preset


def provision(cursor, config, apply=False):
    required = ("business_id", "source_system", "source_tenant", "actors")
    if any(not config.get(key) for key in required):
        raise ValueError("Explicit business, external tenant and actors are required")
    if not isinstance(config["actors"], dict) or len(config["actors"]) > 20:
        raise ValueError("Specify 1–20 actor mappings")
    cursor.execute("SELECT owner_id FROM businesses WHERE id=%s AND is_active IS NOT FALSE", (config["business_id"],))
    business = cursor.fetchone()
    if not business:
        raise ValueError("Active business not found")
    for external_actor, actor in config["actors"].items():
        if not external_actor or not set(actor.get("operations", [])) <= {"prepare", "read", "review"}:
            raise ValueError("Invalid actor operations")
        user = load_actor(cursor, actor["user_id"])
        user["is_superadmin"] = False
        require_permission(cursor, config["business_id"], user, "operations.write")
    blueprint_id = str(uuid.uuid5(uuid.NAMESPACE_URL, CONTRACT + ":" + config["business_id"] + ":" + config["source_system"] + ":" + config["source_tenant"]))
    version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, blueprint_id + ":v1"))
    binding = {**{key: config[key] for key in required}, "version_id": version_id, "enabled": True}
    name = "inbound-case:" + blueprint_id
    cursor.execute("SELECT id FROM agent_clients WHERE organization_name=%s", (name,))
    existing = cursor.fetchone()
    if existing:
        return {"status": "already_provisioned_no_change", "client_id": existing["id"], "version_id": version_id}, None
    if not apply:
        return {"status": "dry_run", "business_id": config["business_id"], "source_system": config["source_system"],
                "source_tenant": config["source_tenant"], "actor_count": len(config["actors"]),
                "preparation_only": True, "external_writes": False, "credits": 0}, None
    cursor.execute("""INSERT INTO agent_blueprints(id,business_id,name,category,status,created_by_user_id,metadata_json)
        VALUES (%s,%s,'Проверка входящих обращений','operations','active',%s,%s::jsonb) ON CONFLICT(id) DO NOTHING""",
        (blueprint_id, config["business_id"], business["owner_id"], json.dumps({"contract": CONTRACT})))
    cursor.execute("""INSERT INTO agent_blueprint_versions(id,blueprint_id,version_number,goal,steps_json,created_by_user_id)
        VALUES (%s,%s,1,'Подготовить обращение и сохранить решение сотрудника без внешних действий',%s::jsonb,%s)
        ON CONFLICT(id) DO NOTHING""", (version_id, blueprint_id, json.dumps(STEPS), business["owner_id"]))
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id=%s", (version_id,))
    validate_preset(cursor.fetchone())
    client = create_agent_client(cursor, owner_user_id=business["owner_id"], organization_name=name,
        contact_email="", allowed_scopes=["cases:prepare", "cases:read", "cases:review"], status="live",
        metadata={"contract": CONTRACT, "inbound_case_bindings": [binding]})
    return {"status": "provisioned", "client_id": client["client_id"], "version_id": version_id,
            "preparation_only": True}, client["agent_key"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--key-file")
    args = parser.parse_args()
    if args.apply and not args.key_file:
        parser.error("--apply requires an exclusive new --key-file")
    with open(args.config) as source:
        config = json.load(source)
    conn = get_db_connection()
    key_created = False
    try:
        result, key = provision(conn.cursor(), config, args.apply)
        if key:
            descriptor = os.open(args.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            key_created = True
            with os.fdopen(descriptor, "w") as target:
                target.write(key + "\n")
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        conn.rollback()
        if key_created:
            os.unlink(args.key_file)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
