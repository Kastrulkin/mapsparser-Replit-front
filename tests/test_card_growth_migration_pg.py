def test_card_growth_schema_is_available_after_migrations(postgres_container, run_migrations):
    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    import psycopg2

    connection = psycopg2.connect(dsn)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.card_growth_cycles'), to_regclass('public.card_state_snapshots')")
        assert cursor.fetchone() == ("card_growth_cycles", "card_state_snapshots")
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='journey_actions'
              AND column_name='growth_cycle_id'
            """
        )
        assert cursor.fetchone() == ("growth_cycle_id",)
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='card_growth_cycles'
              AND column_name IN ('action_completed_at', 'focus_action_json', 'measurement_days_json', 'measurement_json')
            ORDER BY column_name
            """
        )
        assert [row[0] for row in cursor.fetchall()] == ["action_completed_at", "focus_action_json", "measurement_days_json", "measurement_json"]
    finally:
        cursor.close()
        connection.close()
