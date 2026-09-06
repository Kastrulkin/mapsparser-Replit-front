"""Immutable, non-LLM compiled-script artifacts.

The source is an auditable product artifact. It is deliberately never
``exec``'d by the web process: preview and production use a separately
attested sandbox service. A fixed platform implementation is an oracle for
the sheet pilot, never the executor.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from services.llm import LLMTaskRequest, run_llm_task
from services.compiled_json_schema import validate_schema
from services.compiled_table_contract import generation_instructions, normalize_table_input, table_manifest


SCHEMA = "localos_compiled_script_artifact_v1"
PILOT_KIND = "localos.sheet_validate_dedupe_report.v1"
PYTHON_KIND = "localos.python_transform.v1"
MAX_ARTIFACT_BYTES = 192 * 1024
FORBIDDEN_NAMES = {"eval", "exec", "open", "__import__", "compile", "input"}
FORBIDDEN_MODULES = {"os", "subprocess", "socket", "requests", "http", "urllib", "sqlite3", "psycopg", "openai"}


class CompiledArtifactError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def artifact_hash(source: str, manifest: dict[str, Any], fixtures: list[dict[str, Any]]) -> str:
    material = canonical_json({"source": source.replace("\r\n", "\n"), "manifest": manifest, "fixtures": fixtures})
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_candidate(source: Any, manifest: Any, fixtures: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    clean_source = str(source or "").replace("\r\n", "\n").strip()
    clean_manifest = manifest if isinstance(manifest, dict) else {}
    clean_fixtures = fixtures if isinstance(fixtures, list) else []
    if len(canonical_json({"source": clean_source, "manifest": clean_manifest, "fixtures": clean_fixtures}).encode("utf-8")) > MAX_ARTIFACT_BYTES:
        errors.append({"field": "fixtures", "code": "artifact_size_limit", "message": "Общий размер программы и примеров превышает 192 КБ. Уменьшите примеры."})
    if not clean_source or len(clean_source) > 30000:
        errors.append({"field": "source", "code": "source_required", "message": "Нужен Python-исходник до 30 KB."})
    if str(clean_manifest.get("kind") or "") not in {PILOT_KIND, PYTHON_KIND}:
        errors.append({"field": "manifest.kind", "code": "unsupported_kind", "message": "Укажите поддерживаемый pure Python kind."})
    if clean_manifest.get("uses_model") is True or clean_manifest.get("runtime_model_steps"):
        errors.append({"field": "manifest", "code": "runtime_ai_forbidden", "message": "В compiled script запрещены runtime AI-вызовы."})
    if clean_manifest.get("external_effects") not in (None, [], False):
        errors.append({"field": "manifest.external_effects", "code": "external_effects_forbidden", "message": "Пилот не выполняет внешних действий."})
    if validate_schema(clean_manifest.get("input_schema")) or validate_schema(clean_manifest.get("output_schema")):
        errors.append({"field": "manifest", "code": "schemas_required", "message": "Manifest должен описывать вход и результат."})
    if str(clean_manifest.get("runtime_version") or "") != "python-3.12-restricted-v1":
        errors.append({"field": "manifest.runtime_version", "code": "runtime_version", "message": "Нужна зафиксированная версия restricted runtime."})
    if not str(clean_manifest.get("runner_image_digest") or "").startswith("sha256:"):
        errors.append({"field": "manifest.runner_image_digest", "code": "runner_digest", "message": "Нужен digest образа restricted runner."})
    if not isinstance(clean_manifest.get("dependencies"), list) or clean_manifest.get("dependencies"):
        errors.append({"field": "manifest.dependencies", "code": "dependencies_forbidden", "message": "В первом runtime зависимости запрещены."})
    if not clean_fixtures:
        errors.append({"field": "fixtures", "code": "fixtures_required", "message": "Добавьте независимый тестовый пример."})
    if len(clean_fixtures) > 20:
        errors.append({"field": "fixtures", "code": "too_many_fixtures", "message": "Допустимо не более 20 тестовых примеров."})
    for index, fixture in enumerate(clean_fixtures):
        if not isinstance(fixture, dict) or not isinstance(fixture.get("input"), dict):
            errors.append({"field": f"fixtures[{index}]", "code": "fixture_input", "message": "Fixture должен содержать object input."})
            continue
        if fixture.get("source") not in {"user", "generator", "platform"}:
            errors.append({"field": f"fixtures[{index}].source", "code": "fixture_source", "message": "Укажите источник fixture: user или generator."})
        if fixture.get("source") == "user" and "expected" not in fixture:
            errors.append({"field": f"fixtures[{index}].expected", "code": "fixture_expected", "message": "Пользовательский fixture требует ожидаемый результат."})
    if "table_contract" in clean_manifest:
        try:
            expected_manifest = table_manifest(clean_manifest["table_contract"], clean_manifest.get("runner_image_digest"))
            if clean_manifest != expected_manifest:
                raise ValueError("table_manifest_mismatch")
            for fixture in clean_fixtures:
                normalize_table_input(fixture.get("input"), clean_manifest["table_contract"]["columns"])
        except (ValueError, AttributeError):
            errors.append({"field": "manifest.table_contract", "code": "table_contract_invalid", "message": "Таблица и правила должны соответствовать утверждаемому формату."})
    if clean_source:
        try:
            tree = ast.parse(clean_source, mode="exec")
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    errors.append({"field": "source", "code": "imports_forbidden", "message": "В первом runtime imports запрещены."})
                if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                    errors.append({"field": "source", "code": "forbidden_builtin", "message": "Исходник содержит запрещённый builtin."})
                if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr not in {"get", "strip", "lower", "upper", "items", "append", "split", "join"}):
                    errors.append({"field": "source", "code": "forbidden_attribute", "message": "Исходник использует недопустимый attribute access."})
        except SyntaxError:
            errors.append({"field": "source", "code": "syntax", "message": "Python-исходник не разбирается."})
    return {"valid": not errors, "errors": errors, "source": clean_source, "manifest": clean_manifest, "fixtures": clean_fixtures}




def build_artifact(source: Any, manifest: Any, fixtures: Any, compiler_provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    checked = validate_candidate(source, manifest, fixtures)
    if not checked["valid"]:
        raise CompiledArtifactError("invalid compiled script artifact")
    return {
        "schema": SCHEMA,
        "kind": checked["manifest"].get("kind"),
        "source": checked["source"],
        "manifest": checked["manifest"],
        "fixtures": checked["fixtures"],
        "artifact_hash": artifact_hash(checked["source"], checked["manifest"], checked["fixtures"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compiler_provenance": compiler_provenance if isinstance(compiler_provenance, dict) else {},
        "runtime_ai": False,
        "external_effects": False,
    }


def validate_artifact(value: Any) -> dict[str, Any]:
    artifact = value if isinstance(value, dict) else {}
    checked = validate_candidate(artifact.get("source"), artifact.get("manifest"), artifact.get("fixtures"))
    expected = artifact_hash(checked["source"], checked["manifest"], checked["fixtures"])
    if artifact.get("schema") != SCHEMA:
        checked["errors"].append({"field": "schema", "code": "schema", "message": "Неподдерживаемый формат артефакта."})
    if artifact.get("artifact_hash") != expected:
        checked["errors"].append({"field": "artifact_hash", "code": "hash_mismatch", "message": "Артефакт был изменён после проверки."})
    if artifact.get("kind") != checked["manifest"].get("kind"):
        checked["errors"].append({"field": "kind", "code": "kind_mismatch", "message": "Вид программы не соответствует утверждённому формату."})
    checked["valid"] = not checked["errors"]
    checked["artifact_hash"] = expected
    return checked


def generate_candidate_from_description(
    description: str,
    *,
    business_id: str,
    user_id: str,
    generator: Any = None,
    runner_image_digest: str | None = None,
    table_contract: dict[str, Any] | None = None,
    validation_fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Use a model only at compile time and return a checked candidate, never a fallback script."""
    prompt = """You generate one LocalOS compiled Python script. Return JSON only with source, manifest and fixtures.
Permitted manifest.kind values are localos.sheet_validate_dedupe_report.v1 and localos.python_transform.v1. Set
runtime_version to python-3.12-restricted-v1 and dependencies to []. Define process(input_payload), which returns
JSON-serializable data. No imports, eval, exec, files, network, database clients, AI SDKs, external actions, or
runtime model calls. Include at least one fixture with input rows. The platform runs the approved source in a separate
restricted runner and compares pilot fixtures with an independent oracle.
Schemas support only type, properties, required, additionalProperties, items, enum and the documented size/number limits; do not emit other JSON Schema keywords.
User process: """ + str(description or "")[:3000]
    if table_contract is not None:
        prompt += generation_instructions(table_contract)
    try:
        raw = generator(prompt) if generator else run_llm_task(
            LLMTaskRequest(task_key="compiled_script_generation", prompt=prompt, business_id=business_id, user_id=user_id, prompt_version="compiled_script_v1")
        ).content
        parsed = json.loads(str(raw or ""))
    except Exception as error:
        return {"status": "generation_failed", "error": str(error)}
    if not isinstance(parsed, dict):
        return {"status": "generation_failed", "error": "generator_returned_invalid_json"}
    # Deployment identity is supplied by the server, never guessed by the model.
    manifest = parsed.get("manifest") if isinstance(parsed.get("manifest"), dict) else {}
    if table_contract is not None:
        parsed["manifest"] = table_manifest(table_contract, runner_image_digest)
    elif runner_image_digest:
        parsed["manifest"] = {**manifest, "runner_image_digest": runner_image_digest}
    if table_contract is not None and validation_fixtures is not None:
        parsed["fixtures"] = validation_fixtures
    elif isinstance(parsed.get("fixtures"), list):
        parsed["fixtures"] = [{**fixture, "source":"generator"} for fixture in parsed["fixtures"] if isinstance(fixture, dict)]
    checked = validate_candidate(parsed.get("source"), parsed.get("manifest"), parsed.get("fixtures"))
    return {"status": "ready" if checked["valid"] else "needs_fix", "candidate": checked}
