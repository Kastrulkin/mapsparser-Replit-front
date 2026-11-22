"""Adapters to the actual upstream libraries, shared by pilot and runtime."""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    start: int
    end: int
    kind: str
    score: float = 1.0


@dataclass(repr=False)
class EngineResult:
    text: str
    findings: list[Finding]
    replacements: dict[str, str] = field(default_factory=dict)
    restored_text: str | None = None


class Engine(Protocol):
    def scan(self, text: str) -> EngineResult: ...


def language_for(text):
    return "ru" if re.search("[А-Яа-яЁё]", text) else "en"


class PiighostPresidioEngine:
    """Compact RU/EN spaCy models; no downloads or remote recognizers at runtime."""

    def __init__(self):
        import spacy.util
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import SpacyNlpEngine
        from presidio_analyzer.predefined_recognizers import EmailRecognizer
        from tldextract import TLDExtract
        from piighost.components.detector.ner.presidio import PresidioDetector
        from piighost.pipeline import AnonymizationPipeline
        from piighost.components.placeholder import RedactPlaceholderFactory
        from piighost.observation import NoOpTracer

        models = {"en": "en_core_web_sm", "ru": "ru_core_news_sm"}
        if any(not spacy.util.is_package(model) for model in models.values()):
            raise RuntimeError("PII_MODELS_NOT_INSTALLED")
        nlp = SpacyNlpEngine(models=[{"lang_code": lang, "model_name": model}
                                    for lang, model in models.items()])
        analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=list(models))
        # Upstream's default email validator lazily fetches a public suffix list.
        # Use its bundled snapshot only; detection must never make HTTP requests.
        extract = TLDExtract(suffix_list_urls=(), cache_dir=None)

        class OfflineEmailRecognizer(EmailRecognizer):
            def validate_result(self, pattern_text):
                return extract(pattern_text).fqdn != ""

        analyzer.registry.recognizers = [
            OfflineEmailRecognizer(supported_language=item.supported_language)
            if isinstance(item, EmailRecognizer) else item
            for item in analyzer.registry.recognizers
        ]
        self.pipelines = {}
        for lang in models:
            pipeline = AnonymizationPipeline(PresidioDetector(analyzer, language=lang),
                                             observation_redactor=RedactPlaceholderFactory())
            # The pinned upstream version has no public tracer injection port.
            # Disable its payload traces even when the host has an active OTel SDK:
            # redacting only detected spans could still expose undetected text.
            pipeline._tracer = NoOpTracer()
            self.pipelines[lang] = pipeline

    def scan(self, text):
        pipeline = self.pipelines[language_for(text)]
        result = asyncio.run(pipeline.anonymize(text))
        findings = [Finding(item.span.start, item.span.end, item.label, item.confidence)
                    for entity in result.tokens for item in entity.detections]
        return EngineResult(result.text, findings,
                            {str(token): entity.text for entity, token in result.tokens.items()},
                            pipeline.deanonymize(result.text, result.tokens))


class PreserveEngine:
    """Same small NLP models; large gazetteer and local LLM deliberately disabled."""

    def __init__(self):
        import spacy.util
        from preserve import PreserveConfig, Scrubber
        from preserve.config import SensitivityLevel

        models = {"en": "en_core_web_sm", "ru": "ru_core_news_sm"}
        if any(not spacy.util.is_package(model) for model in models.values()):
            raise RuntimeError("PII_MODELS_NOT_INSTALLED")
        self.scrubbers = {
            lang: Scrubber(PreserveConfig(sensitivity_level=SensitivityLevel.AGGRESSIVE,
                                         use_ner=True, spacy_model=model,
                                         use_name_scorer=False, use_normalcy_scanner=False,
                                         use_llm_review=False, ner_labels=["PERSON", "PER", "GPE", "FAC", "ORG"]))
            for lang, model in models.items()
        }

    def scan(self, text):
        result = self.scrubbers[language_for(text)].scrub(text)
        return EngineResult(result.sanitized_text,
                            [Finding(item.start, item.end, item.replacement_type, item.confidence)
                             for item in result.detections], result.placeholder_map.entries,
                            result.placeholder_map.restore(result.sanitized_text))


def make_engine(name):
    if name == "piighost_presidio":
        return PiighostPresidioEngine()
    if name == "preserve":
        return PreserveEngine()
    raise ValueError("PII_ENGINE_UNKNOWN")
