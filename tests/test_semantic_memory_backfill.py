from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backfill_is_bounded_and_keeps_balance_guard():
    source = (ROOT / "scripts/semantic_memory_backfill.py").read_text()

    assert "min(args.workers, 4)" in source
    assert "min(args.embedding_batch, 64)" in source
    assert "min(args.source_batch, 10000)" in source
    assert '"balance_guard" in terminal' in source
    assert "process_embedding_jobs" in source
    assert "enqueue_document_chunks" in source
