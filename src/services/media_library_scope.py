"""A branch may use its own photos and the explicit parent library, not siblings."""

PHOTO_LIBRARY_SCOPE_SQL = """SELECT library.id
    FROM businesses target
    JOIN businesses library ON library.id = target.id
        OR (library.id = target.network_id AND library.network_id = target.network_id)
    WHERE target.id = %s"""

PHOTO_USAGE_LIBRARY_SCOPE_SQL = PHOTO_LIBRARY_SCOPE_SQL.replace('%s', 'usage.business_id')
PHOTO_PUBLICATION_SQL = "metadata_json->>'publication_candidate' IS DISTINCT FROM 'false' AND category IS DISTINCT FROM 'document'"


def available_photo(cursor, asset_id, business_id):
    cursor.execute(
        f"""SELECT id FROM photo_assets WHERE id=%s
            AND business_id IN ({PHOTO_LIBRARY_SCOPE_SQL})
            AND metadata_json->>'disk_import_available' IS DISTINCT FROM 'false'
            AND {PHOTO_PUBLICATION_SQL} LIMIT 1""",
        (asset_id, business_id),
    )
    return cursor.fetchone()
