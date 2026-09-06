"""Backend rollout gate shared by admission, previews and execution."""
import os


def compiled_pilot_allowed(business_id, *, execute=False):
    flag = "COMPILED_SCRIPT_EXECUTE_ENABLED" if execute else "COMPILED_SCRIPT_PREVIEW_ENABLED"
    enabled = os.getenv(flag, "false").strip().lower() in {"1", "true", "yes", "on"}
    cohort = {item.strip() for item in os.getenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", "").split(",") if item.strip()}
    return enabled and bool(business_id) and str(business_id) in cohort
