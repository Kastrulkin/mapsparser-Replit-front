#!/usr/bin/env python3
"""Import 70 batch-three records strictly as unapproved, unqueued drafts."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json, RealDictCursor

from database_manager import get_db_connection


PATH = Path("/app/debug_data/localos-followup-batch-03-final-20260820.json")
EXPECTED_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
DATES = {"2026-08-21": datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc), "2026-08-24": datetime(2026, 8, 24, 7, 0, tzinfo=timezone.utc)}


def main():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if len(items) != 70 or payload.get("base_manifest_canonical_sha256") != EXPECTED_SHA or payload.get("delivery_authorized"):
        raise RuntimeError("final_batch_invalid")
    connection = get_db_connection(); cursor = connection.cursor(cursor_factory=RealDictCursor); imported = []; reused = []
    try:
        for item in items:
            cursor.execute("""SELECT t.*,c.lead_id FROM outreach_campaign_touches t JOIN outreach_campaigns c ON c.id=t.campaign_id WHERE t.id=%s AND t.campaign_id=%s AND c.lead_id=%s FOR UPDATE""", (item["first_touch_id"],item["campaign_id"],item["lead_id"]))
            first = dict(cursor.fetchone() or {})
            if first.get("status") not in {"sent","manual_sent","delivered"}: raise RuntimeError(f"first_not_sent:{item['name']}")
            cursor.execute("SELECT id,status,approved_text,quality_gate_json,delivery_json FROM outreach_campaign_touches WHERE campaign_id=%s AND sequence_index=1",(item["campaign_id"],)); existing=cursor.fetchone()
            if existing and existing["status"] != "cancelled":
                cursor.execute("SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id=%s",(existing["id"],)); queue_count=int((cursor.fetchone() or {}).get("count") or 0)
                if existing["status"] != "draft" or existing.get("approved_text") is not None or queue_count:
                    raise RuntimeError(f"unsafe_existing_second:{item['name']}:{existing['status']}:{queue_count}")
            touch_id=str(existing["id"]) if existing else item["proposed_touch_id"]; draft=item["draft"]; scheduled=DATES[item["planned_send_date"]]
            approval_status=item["approval"]["content_status"]
            quality={**item["quality"],"approval_status":approval_status,"delivery_authorized":False,"batch_id":payload["batch_id"]}
            brief={"observation":draft["observation"],"problem_hypothesis":draft["problem_hypothesis"],"solution":draft["offer_bridge"],"cta":draft["cta"],"source_url":item["evidence"]["research"].get("price_source_url") or item["evidence"]["research"].get("source_url"),"contact_source_url":item["contact_source_url"],"researched_at":item["evidence"]["research"].get("researched_at"),"generation_source":"supervised_v4_followup_batch","first_touch_id":item["first_touch_id"]}
            strategy={"source":"current_public_fact","batch_id":payload["batch_id"],"base_manifest_sha256":EXPECTED_SHA,"first_touch_id":item["first_touch_id"],"angle":draft["angle"],"planned_send_date":item["planned_send_date"],"approval_status":approval_status}
            fingerprint=hashlib.sha256(json.dumps(strategy,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); delivery={"queued":False,"sent":False,"delivery_authorized":False}
            values=(first.get("contact_point_id"),first.get("sender_account_id"),draft["angle"],scheduled,draft["subject"],draft["text"],Json(brief),Json(quality),Json(delivery),fingerprint,Json(strategy),scheduled)
            if existing and existing["status"] != "cancelled":
                touch_id=str(existing["id"])
                if item["planned_send_date"] == "2026-08-24":
                    existing_quality=dict(existing.get("quality_gate_json") or {})
                    existing_quality.update({"approval_status":"blocked_cooldown","delivery_authorized":False,"reason_codes":["gmail_followup_interval_under_72h"],"batch_id":payload["batch_id"]})
                    cursor.execute("UPDATE outreach_campaign_touches SET scheduled_at=%s,manual_due_at=%s,quality_gate_json=%s,delivery_json=%s,updated_at=NOW() WHERE id=%s AND status='draft' AND approved_text IS NULL",(scheduled,scheduled,Json(existing_quality),Json(delivery),touch_id))
                reused.append({"name":item["name"],"touch_id":touch_id,"planned_send_date":item["planned_send_date"]})
            elif existing:
                cursor.execute("""UPDATE outreach_campaign_touches SET channel='email',contact_point_id=%s,sender_account_id=%s,angle_type=%s,scheduled_at=%s,status='draft',subject=%s,generated_text=%s,approved_text=NULL,message_brief_json=%s,quality_gate_json=%s,delivery_json=%s,updated_at=NOW(),strategy_fingerprint=%s,strategy_json=%s,manual_due_at=%s,preflight_at=NULL,preflight_reason=NULL WHERE id=%s AND status='cancelled'""", values+(touch_id,))
            else:
                cursor.execute("""INSERT INTO outreach_campaign_touches(id,campaign_id,draft_id,sequence_index,channel,contact_point_id,sender_account_id,angle_type,scheduled_at,status,subject,generated_text,approved_text,message_brief_json,quality_gate_json,delivery_json,created_at,updated_at,strategy_fingerprint,strategy_json,manual_due_at,preflight_at,preflight_reason) VALUES(%s,%s,NULL,1,'email',%s,%s,%s,%s,'draft',%s,%s,NULL,%s,%s,%s,NOW(),NOW(),%s,%s,%s,NULL,NULL)""",(touch_id,item["campaign_id"])+values)
            cursor.execute("UPDATE outreach_campaigns SET status='draft',updated_at=NOW() WHERE id=%s",(item["campaign_id"],))
            if not (existing and existing["status"] != "cancelled"):
                cursor.execute("INSERT INTO outreach_campaign_events(id,campaign_id,touch_id,event_type,payload_json,created_at) VALUES(%s,%s,%s,'draft_generated',%s,NOW())",(str(uuid.uuid4()),item["campaign_id"],touch_id,Json({"source":"supervised_v4_followup_batch","batch_id":payload["batch_id"],"approval_status":approval_status,"delivery_authorized":False})))
            imported.append({"name":item["name"],"touch_id":touch_id,"planned_send_date":item["planned_send_date"]})
        cursor.execute("SELECT COUNT(*) count FROM outreachsendqueue WHERE campaign_touch_id IN %s",(tuple(x["touch_id"] for x in imported),))
        if int((cursor.fetchone() or {}).get("count") or 0): raise RuntimeError("queue_created")
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally: connection.close()
    print(json.dumps({"group_total":len(imported),"imported_new":len(imported)-len(reused),"reused_existing":len(reused),"ready_aug21":sum(x["planned_send_date"]=="2026-08-21" for x in imported),"deferred_aug24":sum(x["planned_send_date"]=="2026-08-24" for x in imported),"queued":0,"sent":0,"items":imported,"reused_items":reused},ensure_ascii=False))


if __name__ == "__main__": main()
