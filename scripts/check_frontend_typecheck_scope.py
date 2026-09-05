#!/usr/bin/env python3
"""Fail CI when the plan's frontend modules have TypeScript errors.

The wider application has a recorded legacy TypeScript baseline.  This check
still executes the full compiler so transitive imports are checked, then fails
on diagnostics owned by the modules changed in this plan instead of masking
the unrelated baseline.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path
import re
import subprocess
import sys


SCOPED_MODULES = (
    "src/components/DashboardSidebar.tsx",
    "src/components/DashboardLayout.tsx",
    "src/components/prospecting/PartnershipOperationalSections.tsx",
    "src/components/prospecting/partnershipApi.ts",
    "src/components/prospecting/partnershipFlowHelpers.ts",
    "src/components/telegram/PartnershipsMobileModule.tsx",
    "src/config/featureFlags.ts",
    "src/components/agents/CompiledScriptBuilder.tsx",
    "src/pages/dashboard/AgentBlueprintsPage.tsx",
    "src/pages/dashboard/InfluencerPromotionPage.tsx",
    "src/pages/dashboard/InfluencersPage.tsx",
    "src/pages/dashboard/OperatorPage.tsx",
    "src/pages/dashboard/TodayPage.tsx",
    "src/pages/dashboard/MorePage.tsx",
    "src/pages/dashboard/PartnershipSearchPage.tsx",
    "src/pages/dashboard/progressPageCopy.ts",
)


def main() -> int:
    completed = subprocess.run(
        ["npm", "exec", "tsc", "--", "-b", "--force", "--pretty", "false"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    diagnostics = [line for line in completed.stdout.splitlines() if "error TS" in line]
    if completed.returncode and not diagnostics:
        print(completed.stdout)
        print("TypeScript did not produce diagnostics; compilation was not verified.")
        return 1
    if any(not line.startswith("src/") for line in diagnostics):
        print("\n".join(diagnostics))
        return 1
    scoped = [line for line in diagnostics if any(module in line for module in SCOPED_MODULES)]
    pattern = re.compile(r'^(src/.+?)\(\d+,\d+\): error (TS\d+): (.*)$')
    signatures = []
    for line in diagnostics:
        match = pattern.match(line)
        if not match:
            print("Unrecognized TypeScript diagnostic: " + line)
            return 1
        signatures.append(" | ".join(match.groups()))
    baseline_path = Path(__file__).parent / "fixtures/frontend_typecheck_baseline_20260905.json"
    baseline = collections.Counter(json.loads(baseline_path.read_text())["diagnostics"])
    introduced = collections.Counter(signatures) - baseline
    print(f"TypeScript diagnostics: {len(diagnostics)} total; {len(scoped)} scoped-plan")
    print(f"New TypeScript diagnostics anywhere in the application: {sum(introduced.values())}")
    if scoped or introduced:
        print("\n".join(scoped))
        for diagnostic, count in introduced.items():
            print(f"{count} new: {diagnostic}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
