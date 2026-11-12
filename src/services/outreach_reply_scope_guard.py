"""Reject ambiguous recipient-only matching on senders shared by businesses."""


def assert_campaign_peer_isolation(sender_account_id, campaign_id, channel):
    # Replies without an exact thread association cannot be safely assigned by
    # peer if another tenant uses that peer on the same provider identity.
    from pg_db_utils import get_db_connection
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute(r'''SELECT EXISTS (
            SELECT 1 FROM outreachsendqueue requested
            JOIN outreach_campaign_touches requested_touch ON requested_touch.id=requested.campaign_touch_id
            JOIN outreach_campaigns requested_campaign ON requested_campaign.id=requested_touch.campaign_id
            JOIN outreachsendqueue other ON other.sender_account_id=requested.sender_account_id
                AND regexp_replace(regexp_replace(LOWER(BTRIM(other.recipient_value)),
                    '^(https?://)?(www\.)?(t\.me/|telegram\.me/|vk\.com/)|^@','','g'),'/$','')
                  = regexp_replace(regexp_replace(LOWER(BTRIM(requested.recipient_value)),
                    '^(https?://)?(www\.)?(t\.me/|telegram\.me/|vk\.com/)|^@','','g'),'/$','')
            JOIN outreach_campaign_touches other_touch ON other_touch.id=other.campaign_touch_id
            JOIN outreach_campaigns other_campaign ON other_campaign.id=other_touch.campaign_id
            WHERE requested.sender_account_id=%s AND requested_touch.campaign_id=%s
              AND requested.channel=%s AND other.channel=requested.channel
              AND NULLIF(BTRIM(requested.recipient_value),'') IS NOT NULL
              AND other_campaign.business_id IS DISTINCT FROM requested_campaign.business_id
        ) AS ambiguous''',(sender_account_id,campaign_id,channel))
        value=cursor.fetchone()
        if (value.get('ambiguous') if hasattr(value,'get') else value[0]):
            raise PermissionError('reply_peer_scope_ambiguous')
    finally:
        connection.close()
