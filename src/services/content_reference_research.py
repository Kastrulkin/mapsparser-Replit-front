"""Read business-private, dated source research. Never generates or edits posts.

The caller must enforce content read access before calling this projection.
Research is deliberately separate from examples selected for generation.
"""
import hashlib
from services.content_voice_service import _row_to_dict


def get_research(cursor, business_id):
    cursor.execute("""SELECT metadata_json FROM userexamples
        WHERE business_id=%s AND example_type='editorial_source_research'
        AND COALESCE(metadata_json->>'archived','false')<>'true'
        ORDER BY created_at DESC,id DESC LIMIT 1""", (business_id,))
    metadata = _row_to_dict(cursor, cursor.fetchone()).get('metadata_json') or {}
    report = metadata.get('report')
    if not isinstance(report, dict) or report.get('schema_version') != 1:
        return None
    # Defense in depth: even a misplaced record cannot expose another tenant.
    if report.get('business_id') != str(business_id):
        return None
    if not report.get('posts'):
        return {**report, 'stale_post_ids': []}
    cursor.execute('SELECT id,draft_text,theme FROM contentplanitems WHERE business_id=%s', (business_id,))
    current = {str(row['id']): row for row in
               [_row_to_dict(cursor, value) for value in cursor.fetchall()]}
    stale = []
    for post in report.get('posts', []):
        row = current.get(post.get('post_id'))
        if not row or hashlib.sha256(str(row.get('draft_text') or '').encode()).hexdigest() != post.get('text_sha256') or row.get('theme') != post.get('title'):
            stale.append(post.get('post_id'))
    return {**report, 'stale_post_ids': stale}
