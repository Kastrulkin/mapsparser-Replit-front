from pathlib import Path


LEGACY_FILE_LIMITS = {
    "src/api/admin_prospecting.py": 2000,
    "src/services/social_post_service.py": 2000,
    "src/main.py": 2000,
    "frontend/src/components/content-plan/ContentPlanTab.tsx": 2000,
    "frontend/src/pages/dashboard/AgentBlueprintsPage.tsx": 2000,
    "tests/test_agent_blueprint_layer.py": 11824,
}

EXTRACTED_MODULE_ROOTS = (
    "src/api/prospecting",
    "src/services/social_posts",
    "src/legacy_routes",
    "frontend/src/components/content-plan/modules",
    "frontend/src/pages/dashboard/agents",
)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_large_legacy_files_never_grow() -> None:
    for raw_path, maximum in LEGACY_FILE_LIMITS.items():
        path = Path(raw_path)
        if path.exists():
            assert _line_count(path) <= maximum, f"{raw_path} exceeded its ratchet limit of {maximum} lines"


def test_extracted_production_modules_stay_below_two_thousand_lines() -> None:
    for raw_root in EXTRACTED_MODULE_ROOTS:
        root = Path(raw_root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in {".py", ".ts", ".tsx"}:
                assert _line_count(path) <= 2000, f"{path} must be split below 2000 lines"
