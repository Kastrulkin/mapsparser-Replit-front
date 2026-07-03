from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUB_PAGE = ROOT / "frontend/src/pages/dashboard/settings/SettingsHubPage.tsx"
HUB_COMPONENTS = ROOT / "frontend/src/pages/dashboard/settings/SettingsHubComponents.tsx"

BANNED_TERMS = [
    "proxy",
    "preflight",
    "transport",
    "read-only probe",
    "callback delivery",
    "support JSON",
    "support MD",
]


def extract_hub_first_layer(source: str) -> str:
    start = source.index("export const SettingsHubPage")
    detail = source.index("<SettingsDetailSheet", start)
    return source[start:detail]


def main() -> None:
    page_layer = extract_hub_first_layer(HUB_PAGE.read_text(encoding="utf-8"))
    component_source = HUB_COMPONENTS.read_text(encoding="utf-8")
    first_layer_source = "\n".join([page_layer, component_source])
    lowered = first_layer_source.lower()

    failures = [term for term in BANNED_TERMS if term.lower() in lowered]
    if failures:
        joined = ", ".join(failures)
        raise SystemExit(f"Settings hub first layer exposes diagnostics-only terms: {joined}")

    print("ok - settings hub first layer hides diagnostics-only terms")


if __name__ == "__main__":
    main()
