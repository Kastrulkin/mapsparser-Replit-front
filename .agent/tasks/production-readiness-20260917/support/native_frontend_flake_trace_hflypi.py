#!/usr/bin/env python3
"""Trace the two known frontend flakes through a full frozen Vitest run.

This is audit support, not a product test configuration.  It generates an
ephemeral Vite config and transforms only the two candidate tests plus the two
modules whose asynchronous readiness they exercise.  The frozen tree is
verified byte-for-byte before and after the attempt.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time


BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
FRONTEND = SOURCE / "frontend"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
TMP_ROOT = NATIVE / "tmp" / "frontend-flake-trace-v1"
NODE = Path("/usr/local/opt/node@22/bin/node")
NPM = Path("/usr/local/opt/node@22/bin/npm")
GUARD = NATIVE / "unit_network_guard_v5.cjs"
ARCHIVED_GUARD = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре/.agent/tasks/production-readiness-20260917/"
    "evidence/native-frontend-checks-hflypi-20260921/unit_network_guard_v6.cjs"
)
COMMIT = "99849935de26e2932613f2a73cf515dff49104a1"
REPOSITORY = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/"
    "Всякое/SEO с Реплит на Курсоре"
)
MIN_START_BYTES = 5 * 1024**3
MIN_LIVE_BYTES = 2 * 1024**3
TIMEOUT_SECONDS = 900
TRACKED_BLOBS = 5720
ATTEMPT = "v1"
PREFIX = "__HFLYPI_FRONTEND_TRACE__"

LANGUAGE_CONTEXT = "src/i18n/LanguageContext.tsx"
SEO_COMPONENT = "src/components/SEOKeywordsTab.tsx"
SEO_TEST = "src/components/SEOKeywordsTab.i18n.test.tsx"
CONTENT_TEST = "src/pages/dashboard/ContentPage.i18n.test.tsx"
TRACE_MODULES = (LANGUAGE_CONTEXT, SEO_COMPONENT, SEO_TEST, CONTENT_TEST)
TRACE_EXPECTED_SHA256 = {
    LANGUAGE_CONTEXT: "52b4405eac4e26397800cdaefc9436a95fdffd9e13d586ac2d0fb3cba17d6a07",
    SEO_COMPONENT: "ae97ebfe15b48c5254c12145c770a43c55e72924ca0d3db308cee212c13d2360",
    SEO_TEST: "e58c35fc8dcb0ede901fb0671870c276e46fbe7a5f384159093d4af4b789742b",
    CONTENT_TEST: "dbe97fc157d2aa932aa686e9dd1f4746a8e3d550633954619ce0a4e601256cbe",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_bytes() -> int:
    return shutil.disk_usage(BASE).free


def write_json_exclusive(path: Path, payload: object) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        output = os.fdopen(descriptor, "wb")
        try:
            output.write(encoded)
            output.write(b"\n")
        finally:
            output.close()
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def clean_environment() -> dict[str, str]:
    return {
        "NODE_OPTIONS": "--require " + str(GUARD),
        "NO_COLOR": "1",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_CACHE": str(NATIVE / "npm-cache"),
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_USERCONFIG": str(NATIVE / "npm-userconfig-v3.npmrc"),
        "PATH": "/usr/local/opt/node@22/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHON_DOTENV_DISABLED": "1",
        "TMPDIR": str(NATIVE / "tmp"),
    }


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def verify_source_identity() -> dict[str, object]:
    revision = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", COMMIT], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if revision.stdout.strip() != COMMIT:
        raise RuntimeError("frozen source commit did not resolve")
    listing = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-tree", "-rz", "-r", COMMIT], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    mismatches: list[dict[str, str]] = []
    checked = 0
    symlinks = 0
    for record in listing.stdout.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode_raw, object_type_raw, expected_raw = header.split(b" ", 2)
        mode = mode_raw.decode()
        path = SOURCE / os.fsdecode(raw_path)
        if object_type_raw != b"blob":
            mismatches.append({"path": os.fsdecode(raw_path), "reason": "non-blob tree entry"})
            continue
        if mode == "120000":
            symlinks += 1
            payload = os.fsencode(os.readlink(path)) if path.is_symlink() else b""
            observed_mode = "120000" if path.is_symlink() else "missing"
        else:
            payload = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
            observed_mode = format(stat.S_IMODE(path.lstat().st_mode), "06o") if path.exists() else "missing"
        expected_mode = "000755" if mode == "100755" else "000644" if mode == "100644" else mode.zfill(6)
        if git_blob_sha1(payload) != expected_raw.decode() or observed_mode != expected_mode:
            mismatches.append({"path": os.fsdecode(raw_path), "reason": "blob_or_mode_mismatch"})
        checked += 1
    return {"commit": COMMIT, "checked_tracked_blobs": checked, "tracked_symlink_blobs": symlinks,
            "mismatch_count": len(mismatches), "mismatches": mismatches}


def source_hashes() -> dict[str, str]:
    names = [*TRACE_MODULES, "vitest.config.ts", "package.json", "package-lock.json"]
    return {name: sha256(FRONTEND / name) for name in names}


def replace_once(code: str, old: str, new: str, label: str) -> str:
    if code.count(old) != 1:
        raise RuntimeError(f"trace transform anchor {label!r} is not unique")
    return code.replace(old, new, 1)


def generated_plugin() -> str:
    # The transform has no fallback. Any source drift stops the diagnostic rather
    # than silently instrumenting a similar-looking production module.
    return f'''import {{ createHash }} from 'node:crypto';

const prefix = {PREFIX!r};
const files = {json.dumps(list(TRACE_MODULES))};
const filePaths = {json.dumps({name: str(FRONTEND / name) for name in TRACE_MODULES})};
const expected = {json.dumps(TRACE_EXPECTED_SHA256)};
const fingerprint = (value) => createHash('sha256').update(value).digest('hex');
const emitHelper = "\\nconst __hflypiTrace = (phase, fields = {{}}) => globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__?.emit(phase, fields);\\n";

function once(code, oldValue, newValue, label) {{
  if (code.split(oldValue).length !== 2) throw new Error(`hfLYPi trace anchor not unique: ${{label}}`);
  return code.replace(oldValue, newValue);
}}

export function hfLYPiFrontendTrace() {{
  return {{
    name: 'hflypi-frontend-flake-trace-v1',
    enforce: 'pre',
    transform(code, id) {{
      const path = id.split('?')[0];
      const relative = files.find((name) => path === filePaths[name]);
      if (!relative) return null;
      if (fingerprint(code) !== expected[relative]) throw new Error(`hfLYPi trace source hash mismatch: ${{relative}}`);
      let output = code;
      if (relative === {LANGUAGE_CONTEXT!r}) {{
        output = once(output, "import {{ resolveInitialLanguage }} from './languagePreference';", "import {{ resolveInitialLanguage }} from './languagePreference';" + emitHelper, 'language-helper');
        output = once(output, "        const loadedTranslations = await loadTranslations(language);\\n        const fallbackTranslations = (await import('./locales/en')).en;", "        __hflypiTrace('lang.load.start', {{ language }});\\n        const loadedTranslations = await loadTranslations(language);\\n        __hflypiTrace('lang.locale.loaded', {{ language }});\\n        const fallbackTranslations = (await import('./locales/en')).en;\\n        __hflypiTrace('lang.fallback.loaded', {{ language }});", 'language-selected-fallback');
        output = once(output, "        const fallbackTranslations = (await import('./locales/en')).en;\\n\\n        if (active) {{\\n          setTranslations(fallbackTranslations);", "        const fallbackTranslations = (await import('./locales/en')).en;\\n        __hflypiTrace('lang.catch.fallback.loaded', {{ language }});\\n\\n        if (active) {{\\n          setTranslations(fallbackTranslations);", 'language-catch-fallback');
        output = once(output, '          setTranslations(mergeTranslations(fallbackTranslations, loadedTranslations));', "          __hflypiTrace('lang.set.translations', {{ language }});\\n          setTranslations(mergeTranslations(fallbackTranslations, loadedTranslations));", 'language-set');
        output = once(output, '    return <LanguageLoadingFallback />;', "    return <LanguageLoadingFallback />;", 'language-loading-return');
        output = once(output, '  return <LanguageContext.Provider value={{value}}>{{children}}</LanguageContext.Provider>;', "  __hflypiTrace('lang.provider.ready', {{ language }});\\n  return <LanguageContext.Provider value={{value}}>{{children}}</LanguageContext.Provider>;", 'language-ready-return');
      }} else if (relative === {SEO_COMPONENT!r}) {{
        output = once(output, "import {{ useOutletContext }} from 'react-router-dom';", "import {{ useOutletContext }} from 'react-router-dom';" + emitHelper, 'seo-helper');
        output = once(output, '        setLoading(true);', "        __hflypiTrace('seo.load.start', {{ businessId, demoMode, language }});\\n        setLoading(true);", 'seo-load-start');
        output = once(output, '            const demoKeywords = getDemoShowcaseData(language).keywords;', "            const demoKeywords = getDemoShowcaseData(language).keywords;\\n            __hflypiTrace('seo.demo.data', {{ language, count: demoKeywords.length }});", 'seo-demo-data');
        output = once(output, '            setKeywords(demoKeywords);', "            __hflypiTrace('seo.demo.set.keywords', {{ count: demoKeywords.length }});\\n            setKeywords(demoKeywords);", 'seo-demo-keywords');
        output = once(output, '            setGrouped({{ [demoKeywords[0].category]: demoKeywords }});', "            __hflypiTrace('seo.demo.set.grouped', {{ count: demoKeywords.length }});\\n            setGrouped({{ [demoKeywords[0].category]: demoKeywords }});", 'seo-demo-grouped');
        output = once(output, '        loadKeywords();\\n        loadNegativeKeywords();', "        __hflypiTrace('seo.effect.start', {{ businessId, demoMode, language }});\\n        loadKeywords();\\n        loadNegativeKeywords();", 'seo-effect');
        output = once(output, '    return (', "    if (demoMode && keywords.length > 0) __hflypiTrace('seo.keywords.ready', {{ language, count: keywords.length }});\\n\\n    return (", 'seo-render-ready');
      }} else if (relative === {SEO_TEST!r}) {{
        output = once(output, '  beforeEach(() => {{', "  beforeEach(() => {{\\n    globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__?.activate('seo-tr');", 'seo-test-activate');
        output = once(output, '  afterEach(() => {{\\n    vi.unstubAllGlobals();', "  afterEach(() => {{\\n    globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__?.deactivate('seo-tr');\\n    vi.unstubAllGlobals();", 'seo-test-deactivate');
      }} else if (relative === {CONTENT_TEST!r}) {{
        output = once(output, "import {{ beforeEach, describe, expect, it, vi }} from 'vitest';", "import {{ afterEach, beforeEach, describe, expect, it, vi }} from 'vitest';", 'content-test-import');
        output = once(output, '  beforeEach(() => {{', "  beforeEach(() => {{\\n    globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__?.activate('content-i18n');", 'content-test-activate');
        output = once(output, "\\n  it('renders the Greek audience heading", "\\n  afterEach(() => globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__?.deactivate('content-i18n'));\\n\\n  it('renders the Greek audience heading", 'content-test-deactivate');
      }}
      return {{ code: output, map: null }};
    }},
  }};
}}
'''


def generated_setup() -> str:
    return f'''const prefix = {PREFIX!r};
let target = null;
const safeProcess = typeof process === 'undefined' ? null : process;
const worker = safeProcess ? Object.fromEntries(Object.entries(safeProcess.env).filter(([key]) => key.startsWith('VITEST_'))) : {{}};
globalThis.__LOCALOS_HFLYPI_FRONTEND_TRACE__ = {{
  activate(nextTarget) {{ target = nextTarget; this.emit('test.active', {{ target }}); }},
  deactivate(expected) {{ if (target === expected) {{ this.emit('test.complete', {{ target }}); target = null; }} }},
  emit(phase, fields = {{}}) {{
    if (!target) return;
    console.log(prefix + JSON.stringify({{ target, phase, epoch_ms: Date.now(), perf_ms: performance.now(), pid: safeProcess?.pid ?? null, worker, fields }}));
  }},
}};
'''


def generated_reporter(events_path: Path) -> str:
    return f'''import {{ appendFileSync }} from 'node:fs';
const destination = {str(events_path)!r};
const prefix = {PREFIX!r};
const targets = new Set([{SEO_TEST!r}, {CONTENT_TEST!r}]);
let eventCount = 0;
const maxEvents = 200;
const candidate = (module) => targets.has(module.relativeModuleId);
const emit = (kind, value) => {{
  if (eventCount >= maxEvents) throw new Error('hfLYPi frontend trace exceeded 200 events');
  eventCount += 1;
  appendFileSync(destination, JSON.stringify({{ kind, observed_epoch_ms: Date.now(), ...value }}) + '\\n', {{ mode: 0o600 }});
}};
export default class HfLYPiFrontendTraceReporter {{
  onTestModuleStart(module) {{ if (candidate(module)) emit('module.start', {{ module: module.relativeModuleId }}); }}
  onTestModuleEnd(module) {{ if (candidate(module)) emit('module.end', {{ module: module.relativeModuleId, state: module.state(), diagnostic: module.diagnostic() }}); }}
  onTestCaseReady(test) {{ if (candidate(test.module)) emit('case.ready', {{ module: test.module.relativeModuleId, name: test.fullName }}); }}
  onTestCaseResult(test) {{ if (candidate(test.module)) emit('case.result', {{ module: test.module.relativeModuleId, name: test.fullName, result: test.result(), diagnostic: test.diagnostic() }}); }}
  onUserConsoleLog(log) {{
    const frames = log.content.split(prefix).slice(1);
    for (const frame of frames) {{
      const raw = frame.split('\\n', 1)[0].trim();
      try {{ emit('runtime.trace', {{ task_id: log.taskId ?? null, vitest_epoch_ms: log.time, trace: JSON.parse(raw) }}); }}
      catch (error) {{ emit('runtime.invalid', {{ task_id: log.taskId ?? null, raw, error: String(error) }}); }}
    }}
  }}
}}
'''


def generated_config(plugin_path: Path, setup_path: Path, reporter_path: Path, cache_dir: Path) -> str:
    return f'''import base from {str(FRONTEND / 'vitest.config.ts')!r};
import {{ hfLYPiFrontendTrace }} from {str(plugin_path)!r};

export default {{
  ...base,
  cacheDir: {str(cache_dir)!r},
  plugins: [...base.plugins, hfLYPiFrontendTrace()],
  test: {{
    ...base.test,
    setupFiles: [...base.test.setupFiles, {str(setup_path)!r}],
    reporters: ['default', {str(reporter_path)!r}],
  }},
}};
'''


def generated_assets() -> dict[str, Path]:
    if TMP_ROOT.exists():
        raise RuntimeError(f"refusing to reuse trace temporary directory: {TMP_ROOT}")
    TMP_ROOT.mkdir(mode=0o700, parents=True)
    try:
        assets = {
            "plugin": TMP_ROOT / "trace-plugin.mjs",
            "setup": TMP_ROOT / "trace-setup.mjs",
            "reporter": TMP_ROOT / "trace-reporter.mjs",
            "config": TMP_ROOT / "vitest-flake-trace-v1.config.mjs",
            "events": TMP_ROOT / "events.ndjson",
            "cache": TMP_ROOT / "vite-cache",
        }
        assets["plugin"].write_text(generated_plugin())
        assets["setup"].write_text(generated_setup())
        assets["reporter"].write_text(generated_reporter(assets["events"]))
        assets["config"].write_text(generated_config(assets["plugin"], assets["setup"], assets["reporter"], assets["cache"]))
        return assets
    except BaseException:
        shutil.rmtree(TMP_ROOT)
        raise


def terminate_owned_process(process: subprocess.Popen[str]) -> tuple[str, str, str]:
    if process.poll() is not None:
        stdout, stderr = process.communicate(timeout=1)
        return "already_exited", stdout, stderr
    os.killpg(process.pid, signal.SIGTERM)
    try:
        stdout, stderr = process.communicate(timeout=10)
        return "term", stdout, stderr
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=10)
        return "kill", stdout, stderr


def run_full(command: list[str], environment: dict[str, str]) -> dict[str, object]:
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=FRONTEND, env=environment, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    stopped_reason = None
    cleanup_mode = "normal"
    stdout = stderr = ""
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if free_bytes() >= MIN_LIVE_BYTES and time.monotonic() - started < TIMEOUT_SECONDS:
                    continue
                stopped_reason = "disk_floor" if free_bytes() < MIN_LIVE_BYTES else "timeout"
                cleanup_mode, stdout, stderr = terminate_owned_process(process)
                break
    finally:
        if process.poll() is None:
            cleanup_mode, stdout, stderr = terminate_owned_process(process)
    return {"command": command, "exit_code": process.returncode, "stopped_reason": stopped_reason,
            "cleanup_mode": cleanup_mode, "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "stdout": stdout, "stderr": stderr, "free_bytes_after": free_bytes(),
            "environment_keys": sorted(environment)}


def verify_network_guard(environment: dict[str, str]) -> dict[str, object]:
    command = [str(NODE), "-e", (
        "const p=fetch('https://example.invalid'); if(!p||typeof p.then!=='function')throw new Error('fetch not promise'); "
        "p.then(()=>{throw new Error('guard resolved unexpectedly')}).catch(e=>{if(!String(e.message).includes('hfLYPi unit network guard denied'))throw e; console.log('network-guard-active')});"
    )]
    try:
        completed = subprocess.run(command, cwd=FRONTEND, env=environment, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15)
    except subprocess.TimeoutExpired:
        raise RuntimeError("frontend trace network guard negative probe timed out")
    result = {"command": command, "exit_code": completed.returncode,
              "stdout": completed.stdout, "stderr": completed.stderr}
    if completed.returncode != 0 or completed.stdout.strip() != "network-guard-active":
        raise RuntimeError("frontend trace network guard negative probe failed")
    return result


def copy_trace_inputs(assets: dict[str, Path]) -> dict[str, str]:
    copied: dict[str, str] = {}
    for name in ("plugin", "setup", "reporter", "config"):
        destination = EVIDENCE / f"native-frontend-flake-trace-{name}-{ATTEMPT}"
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            output = os.fdopen(descriptor, "wb")
            try:
                output.write(assets[name].read_bytes())
            finally:
                output.close()
        except BaseException:
            try:
                destination.unlink()
            except FileNotFoundError:
                pass
            raise
        copied[destination.name] = sha256(destination)
    return copied


def read_events(path: Path) -> list[object]:
    if not path.exists():
        return []
    events: list[object] = []
    for line in path.read_text().splitlines():
        events.append(json.loads(line))
    return events


def main() -> int:
    if free_bytes() < MIN_START_BYTES:
        raise RuntimeError("insufficient free disk before trace start")
    if not FRONTEND.is_dir() or not (FRONTEND / "node_modules").is_dir() or not NODE.is_file() or not NPM.is_file():
        raise RuntimeError("frozen frontend dependencies are unavailable")
    if not GUARD.is_file() or not ARCHIVED_GUARD.is_file():
        raise RuntimeError("active or archived frontend network guard is unavailable")
    if sha256(GUARD) != sha256(ARCHIVED_GUARD):
        raise RuntimeError("active frontend network guard differs from reviewed v6 guard")
    raw_path = EVIDENCE / f"native-frontend-unit-full-trace-{ATTEMPT}.json"
    event_path = EVIDENCE / f"native-frontend-unit-full-trace-events-{ATTEMPT}.json"
    manifest_path = EVIDENCE / f"native-frontend-unit-full-trace-manifest-{ATTEMPT}.json"
    copied_paths = tuple(EVIDENCE / f"native-frontend-flake-trace-{name}-{ATTEMPT}"
                         for name in ("plugin", "setup", "reporter", "config"))
    if any(path.exists() for path in (raw_path, event_path, manifest_path, *copied_paths)):
        raise RuntimeError("refusing to overwrite frontend trace evidence")
    pre_hashes = source_hashes()
    pre_identity = verify_source_identity()
    if pre_identity["checked_tracked_blobs"] != TRACKED_BLOBS or pre_identity["mismatch_count"] != 0:
        raise RuntimeError("frozen source identity differs before trace")
    tmp_owned = False
    assets: dict[str, Path] = {}
    result: dict[str, object] | None = None
    trace_events: list[object] = []
    guard_probe: dict[str, object] | None = None
    cleanup_error = None
    acceptance_error = None
    try:
        assets = generated_assets()
        tmp_owned = True
        env = clean_environment()
        guard_probe = verify_network_guard(env)
        result = run_full([str(NPM), "test", "--", "--config", str(assets["config"])], env)
        write_json_exclusive(raw_path, result)
        trace_events = read_events(assets["events"])
        write_json_exclusive(event_path, {"event_count": len(trace_events), "events": trace_events})
        copied_hashes = copy_trace_inputs(assets)
    finally:
        post_hashes = source_hashes()
        post_identity = verify_source_identity()
        if tmp_owned and TMP_ROOT.exists():
            try:
                shutil.rmtree(TMP_ROOT)
            except BaseException:
                cleanup_error = str(sys.exception())
        manifest = {"attempt": ATTEMPT, "scope": "Full frozen 830-test default-worker diagnostic; no product source mutation.",
                    "command": result.get("command") if result else None, "default_worker_configuration": True,
                    "max_workers_override": False, "timeout_override": False, "assertions_modified": False,
                    "network_guard_path": str(GUARD), "network_guard_sha256": sha256(GUARD),
                    "archived_network_guard_path": str(ARCHIVED_GUARD),
                    "archived_network_guard_sha256": sha256(ARCHIVED_GUARD),
                    "network_guard_probe": guard_probe,
                    "pre_source_hashes": pre_hashes, "post_source_hashes": post_hashes,
                    "source_hashes_unchanged": pre_hashes == post_hashes,
                    "pre_source_identity": pre_identity, "post_source_identity": post_identity,
                    "temporary_trace_input_hashes": locals().get("copied_hashes", {}),
                    "temporary_directory_removed": not TMP_ROOT.exists(), "cleanup_error": cleanup_error,
                    "trace_event_count": len(trace_events)}
        candidate_results = sum(
            1 for event in trace_events
            if isinstance(event, dict) and event.get("kind") == "case.result"
        )
        runtime_events = sum(
            1 for event in trace_events
            if isinstance(event, dict) and event.get("kind") == "runtime.trace"
        )
        full_830_reported = bool(result and "(830)" in str(result.get("stdout", "")))
        trace_complete = candidate_results == 3 and runtime_events > 0 and len(trace_events) <= 200
        manifest.update({"candidate_case_result_count": candidate_results,
                         "runtime_trace_event_count": runtime_events,
                         "full_830_reported": full_830_reported,
                         "trace_complete": trace_complete})
        if cleanup_error is not None or TMP_ROOT.exists():
            acceptance_error = "temporary_trace_cleanup_incomplete"
        elif post_hashes != pre_hashes or post_identity["checked_tracked_blobs"] != TRACKED_BLOBS or post_identity["mismatch_count"] != 0:
            acceptance_error = "frozen_source_changed_or_identity_invalid"
        elif sha256(GUARD) != sha256(ARCHIVED_GUARD):
            acceptance_error = "network_guard_changed"
        elif guard_probe is None:
            acceptance_error = "network_guard_probe_missing"
        elif not full_830_reported:
            acceptance_error = "full_830_count_not_reported"
        elif not trace_complete:
            acceptance_error = "trace_incomplete"
        elif not result or result["exit_code"] or result["stopped_reason"]:
            acceptance_error = "vitest_nonzero_or_interrupted"
        manifest["acceptance_error"] = acceptance_error
        write_json_exclusive(manifest_path, manifest)
    if result is None:
        raise RuntimeError("trace did not start")
    if acceptance_error or result["exit_code"] or result["stopped_reason"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
