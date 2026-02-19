# Статусы parsequeue: единый канонический набор, чтобы не разъезжалось.
# Чтение должно учитывать и старый 'done' (для уже существующих записей).
# Запись/обновление всегда использует STATUS_COMPLETED.

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"
STATUS_CAPTCHA = "captcha"

# Все канонические статусы (для валидации/подсказок)
STATUSES = frozenset({
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_CAPTCHA,
})

# При чтении: считаем задачу «завершённой», если статус completed или legacy done
COMPLETED_ALIASES = (STATUS_COMPLETED, "done")


def normalize_status(raw: str | None) -> str:
    """Привести статус к каноническому (для ответов API)."""
    if not raw:
        return STATUS_PENDING
    s = (raw or "").strip().lower()
    if s == "done":
        return STATUS_COMPLETED
    return s if s in STATUSES else raw


def is_finished(status: str | None) -> bool:
    """Задача в завершённом состоянии (completed или старый done)."""
    return (status or "").strip() in COMPLETED_ALIASES
