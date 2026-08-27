from datetime import datetime, timezone

from services import community_topic_trends


def test_topic_percentages_use_full_sample_denominator():
    topics = community_topic_trends._normalize_percentages(
        [
            {"title": "Первая", "sample_count": 31},
            {"title": "Вторая", "sample_count": 19},
            {"title": "Третья", "sample_count": 10},
        ],
        100,
    )

    assert [item["percent"] for item in topics] == [31, 19, 10]


def test_topic_labeling_task_is_registered_for_public_semantic_analysis():
    from services.llm.registry import get_task_definition

    definition = get_task_definition("community_topic_labeling")

    assert definition is not None
    assert definition.primary_provider == "gigachat"
    assert definition.data_class == "public"


def test_fallback_label_comes_from_real_cluster_text():
    label = community_topic_trends._fallback_label(
        [
            "Пустые окна — не норма\nСегодня обсуждаем работу администратора.",
            "Как возвращать гостей после отмены записи?",
        ],
        0,
    )

    assert label == "Пустые окна — не норма"


def test_snapshot_loader_keeps_five_ranked_semantic_topics():
    class Cursor:
        description = [
            ("period_key",), ("period_days",), ("message_count",), ("sample_size",),
            ("topics_json",), ("analysis_method",), ("generated_at",),
        ]

        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return [(
                "month",
                30,
                1500,
                900,
                [
                    {"key": f"semantic-{index}", "title": f"Тема {index}", "percent": 20 - index}
                    for index in range(7)
                ],
                "embedding_kmeans_v1",
                datetime(2026, 8, 27, tzinfo=timezone.utc),
            )]

    result = community_topic_trends._load_snapshots(Cursor(), "fingerprint")

    assert len(result[0]["topics"]) == 5
    assert result[0]["analysis_method"] == "semantic_embeddings"
    assert result[0]["sample_size"] == 900


def test_topic_trends_stay_empty_until_snapshot_migration_exists():
    class Cursor:
        def execute(self, query, _params=None):
            assert "TO_REGCLASS" in query

        def fetchone(self):
            return (None,)

    result = community_topic_trends.load_topic_trends(
        Cursor(),
        ["source-1"],
        datetime(2026, 8, 27, tzinfo=timezone.utc),
    )

    assert result == []
