#!/usr/bin/env python3
"""Static guardrails for the audit-only frontend flake trace launcher."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile


SOURCE = Path(__file__).with_name("native_frontend_flake_trace_hflypi.py")
text = SOURCE.read_text()
required = (
    '"--config", str(assets["config"])',
    '"max_workers_override": False',
    '"timeout_override": False',
    '"assertions_modified": False',
    '"NODE_OPTIONS": "--require " + str(GUARD)',
    'ARCHIVED_GUARD',
    'guard_probe = verify_network_guard(env)',
    'network-guard-active',
    "enforce: 'pre'",
    'verify_source_identity()',
    'TRACKED_BLOBS = 5720',
    'shutil.rmtree(TMP_ROOT)',
    'SEOKeywordsTab.i18n.test.tsx',
    'ContentPage.i18n.test.tsx',
    'LanguageContext.tsx',
    'SEOKeywordsTab.tsx',
)
for marker in required:
    if marker not in text:
        raise SystemExit(f"missing trace control marker: {marker}")
for forbidden in ('--maxWorkers', 'testTimeout', 'hookTimeout', 'vi.mock', 'source.write_text', "enforce: 'post'"):
    if forbidden in text:
        raise SystemExit(f"forbidden trace widening marker: {forbidden}")
spec = importlib.util.spec_from_file_location("trace_launcher", SOURCE)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load trace launcher for generated-plugin control")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
raw_tmp = tempfile.mkdtemp(prefix="hflypi-frontend-trace-control-")
tmp = Path(raw_tmp)
try:
    plugin_path = tmp / "trace-plugin.mjs"
    runner_path = tmp / "check.mjs"
    plugin_path.write_text(launcher.generated_plugin())
    setup_path = tmp / "trace-setup.mjs"
    reporter_path = tmp / "trace-reporter.mjs"
    config_path = tmp / "vitest-flake-trace-v1.config.mjs"
    setup_path.write_text(launcher.generated_setup())
    reporter_path.write_text(launcher.generated_reporter(tmp / "events.ndjson"))
    config_path.write_text(launcher.generated_config(plugin_path, setup_path, reporter_path, tmp / "vite-cache"))
    modules = {name: str(launcher.FRONTEND / name) for name in launcher.TRACE_MODULES}
    runner_path.write_text(
        "import { readFileSync } from 'node:fs';\n"
        "import { hfLYPiFrontendTrace } from './trace-plugin.mjs';\n"
        "import Reporter from './trace-reporter.mjs';\n"
        f"import {{ loadConfigFromFile }} from {str(launcher.FRONTEND / 'node_modules/vite/dist/node/index.js')!r};\n"
        f"const modules = {modules!r};\n"
        "const transform = hfLYPiFrontendTrace().transform;\n"
        "for (const path of Object.values(modules)) {\n"
        "  const result = transform(readFileSync(path, 'utf8'), path);\n"
        "  if (!result || typeof result.code !== 'string') throw new Error('raw module was not transformed: ' + path);\n"
        "}\n"
        "let rejected = false;\n"
        "try { transform(readFileSync(modules['src/i18n/LanguageContext.tsx'], 'utf8') + '\\n ', modules['src/i18n/LanguageContext.tsx']); }\n"
        "catch { rejected = true; }\n"
        "if (!rejected) throw new Error('drifted module was accepted');\n"
        "const reporter = new Reporter();\n"
        "if (typeof reporter.onTestModuleStart !== 'function' || typeof reporter.onUserConsoleLog !== 'function') throw new Error('reporter did not instantiate');\n"
        f"const prefix = {launcher.PREFIX!r};\n"
        "reporter.onUserConsoleLog({ content: prefix + JSON.stringify({ phase: 'one' }) + '\\n' + prefix + JSON.stringify({ phase: 'two' }), taskId: 'combined', time: 1 });\n"
        f"const combined = readFileSync({str(tmp / 'events.ndjson')!r}, 'utf8').trim().split('\\n').map(JSON.parse);\n"
        "if (combined.length !== 2 || combined.some((event) => event.kind !== 'runtime.trace')) throw new Error('combined console frames were not split');\n"
        f"const loaded = await loadConfigFromFile({{ command: 'serve', mode: 'test' }}, {str(config_path)!r}, {str(launcher.FRONTEND)!r}, 'silent');\n"
        "if (!loaded || !loaded.config || !Array.isArray(loaded.config.plugins) || !loaded.config.plugins.some((plugin) => plugin.name === 'hflypi-frontend-flake-trace-v1')) throw new Error('generated config did not load trace plugin');\n"
        "if (!Array.isArray(loaded.config.test?.setupFiles) || loaded.config.test.setupFiles.length !== 2) throw new Error('generated config did not preserve+append setup');\n"
        "console.log('generated-plugin-raw-and-drift-controls: PASS');\n"
    )
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is unavailable for generated-plugin control")
    completed = subprocess.run([node, str(runner_path)], text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, check=False, timeout=30)
    if completed.returncode != 0 or completed.stdout.strip() != "generated-plugin-raw-and-drift-controls: PASS":
        raise SystemExit("generated-plugin control failed: " + completed.stderr)
    for generated in (plugin_path, setup_path, reporter_path, config_path):
        parsed = subprocess.run([node, "--check", str(generated)], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, timeout=30)
        if parsed.returncode != 0:
            raise SystemExit("generated trace asset parse failed: " + parsed.stderr)
finally:
    shutil.rmtree(tmp)

print("native frontend flake trace controls: PASS")
