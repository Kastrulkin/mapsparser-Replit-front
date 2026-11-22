"""Server-owned, tenant-bound public spans; never infer trust from prompt labels."""

from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class PublicSpan:
    business_id: str
    source_id: str
    kind: str
    start: int
    end: int
    value: str


def validated_public_spans(text, business_id, policy, context):
    if not isinstance(context, tuple) or len(context) > 100:
        raise ValueError("PII_PUBLIC_CONTEXT_INVALID")
    if context and policy not in {"public_geo", "content"}:
        raise ValueError("PII_PUBLIC_CONTEXT_INVALID")
    spans = []
    for item in context:
        if (not isinstance(item, PublicSpan) or item.business_id != business_id
                or not isinstance(item.source_id, str) or not item.source_id or len(item.source_id) > 200
                or not isinstance(item.kind, str) or item.kind not in {"ORGANIZATION", "ADDRESS"}
                or not isinstance(item.start, int) or isinstance(item.start, bool)
                or not isinstance(item.end, int) or isinstance(item.end, bool)
                or not 0 <= item.start < item.end <= len(text)
                or not isinstance(item.value, str) or not 1 <= len(item.value) <= 300
                or text[item.start:item.end] != item.value):
            raise ValueError("PII_PUBLIC_CONTEXT_INVALID")
        spans.append((item.start, item.end))
    return tuple(spans)
