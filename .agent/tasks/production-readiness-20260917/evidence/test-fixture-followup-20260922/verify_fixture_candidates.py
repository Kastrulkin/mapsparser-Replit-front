"""Bounded offline red/green proof for two existing dirty test candidates.

This verifier is intentionally separate from the frozen aggregate runner.  It
only executes copies under writable/fixture-candidates through that runner's
already-reviewed sandbox invocation, retaining structured metadata rather than
pytest output.  It does not adopt either candidate into the source tree.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path("/private/tmp/localos-current-full-v10.BYwJr6")
SOURCE = ROOT / "source"
EVIDENCE = ROOT / "evidence"
FIXTURES = ROOT / "writable" / "fixture-candidates"
DESTINATION = EVIDENCE / "fixture-candidates-v1.json"
RUNNER = ROOT / "run_current_full_v10.py"
POLICY = ROOT / "policy-v10.sb"
HELPER = ROOT / "owned_processes.py"
PSUTIL = Path("/private/tmp/localos-content-perf-deps.7zNvCi/python")
MARK = "FIXTURE_CANDIDATES_V1="

RUNNER_SHA = "93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4"
POLICY_SHA = "e41663b03dfe1a0be7b27bb6fcb96abf27d302633464e7a8fd77d86e54d39201"
HELPER_SHA = "4f16b6c343223717dcf3b5bdbf86ff9159594b33fa92d744527891188c4c227b"
EXPECTED = {
    "clean/tests/test_author_daily_gate.py": "3078d14462592254229dd84243402a6ed00bac0778938b4009a7b73a7b5d028a",
    "dirty/tests/test_author_daily_gate.py": "21a1a4c9c3337bb516a8c80a354b860d6ba380bf1c4ce0aed4ba0bc5196f782c",
    "clean/tests/test_legacy_parser_diagnostic_logs.py": "02c78388dcbf3729675a5f327cf3888b17e1e9dcded36b21651d10863386df76",
    "dirty/tests/test_legacy_parser_diagnostic_logs.py": "6b36812601c2df579ac660e01976fee066f3c7a3f5bf3e0c7010799838da49ba",
    "clean/src/yandex_maps_scraper.py": "3a069c6724f31990792d74ff217e19ded6a39e24a0512139e4ea21fe9ef423c5",
    "dirty/src/yandex_maps_scraper.py": "3a069c6724f31990792d74ff217e19ded6a39e24a0512139e4ea21fe9ef423c5",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


def load_runner():
    spec = importlib.util.spec_from_file_location("frozen_current_full_v10", RUNNER)
    require(spec is not None and spec.loader is not None, "runner_import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_hashes():
    require(not any(path.is_symlink() for path in FIXTURES.rglob("*")), "fixture_symlink")
    actual = {name: sha(FIXTURES / name) for name in EXPECTED}
    require(actual == EXPECTED, "fixture_hash_drift")
    return actual


def callback(output):
    rows = [line[len(MARK):] for line in output.splitlines() if line.startswith(MARK)]
    require(len(rows) == 1, "callback_count")
    return json.loads(rows[0])


def author_code(candidate):
    target = FIXTURES / candidate / "tests" / "test_author_daily_gate.py"
    node = str(target) + "::test_author_dispatch_uses_creator_bridge_fingerprint_and_fails_closed_on_change"
    return r'''import json,os,pytest,sys
from pathlib import Path
source=Path(%r); fixture=Path(%r); target=%r; mark=%r
sys.path[:0]=[str(source / 'src'),str(source)]
result={'reports':[],'nodes':[],'collection_errors':[]}
class H:
 def pytest_collection_finish(self,session): result['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed: result['collection_errors'].append(report.nodeid)
 @pytest.hookimpl(hookwrapper=True)
 def pytest_runtest_makereport(self,item,call):
  outcome=yield; report=outcome.get_result(); failure=None
  if report.failed and call.excinfo is not None:
   frames=[]
   for frame in call.excinfo.traceback:
    path=str(frame.path)
    for root,label in [(str(source),'source'),(str(fixture),'fixture'),(sys.prefix,'venv')]:
     if path.startswith(root+'/'):
      frames.append({'path':label+path[len(root):],'line':frame.lineno+1}); break
   failure={'exception_type':type(call.excinfo.value).__name__,'frames':frames[-12:]}
  report.safe_failure=failure
 def pytest_runtest_logreport(self,report):
  result['reports'].append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'xfail':bool(getattr(report,'wasxfail',False)),'failure':getattr(report,'safe_failure',None)})
code=pytest.main([target,'-q','-c',str(source/'pytest.ini'),'-p','no:cacheprovider','--tb=no','--show-capture=no','--basetemp',str(fixture/'basetemp-author')],plugins=[H()])
result['return_code']=code
print(mark+json.dumps(result,sort_keys=True));raise SystemExit(code)
''' % (str(SOURCE), str(FIXTURES), node, MARK)


def diagnostic_code(candidate):
    target = FIXTURES / candidate / "tests" / "test_legacy_parser_diagnostic_logs.py"
    node = str(target) + "::LegacyParserDiagnosticLogsTests"
    return r'''import json,os,pytest,subprocess,sys
from pathlib import Path
source=Path(%r); fixture=Path(%r); target=%r; mark=%r
sys.path[:0]=[str(source / 'src'),str(source)]
result={'reports':[],'nodes':[],'collection_errors':[]}
class H:
 def pytest_collection_finish(self,session): result['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed: result['collection_errors'].append(report.nodeid)
 @pytest.hookimpl(hookwrapper=True)
 def pytest_runtest_makereport(self,item,call):
  outcome=yield; report=outcome.get_result(); failure=None
  if report.failed and call.excinfo is not None:
   frames=[]
   for frame in call.excinfo.traceback:
    path=str(frame.path)
    for root,label in [(str(source),'source'),(str(fixture),'fixture'),(sys.prefix,'venv')]:
     if path.startswith(root+'/'):
      frames.append({'path':label+path[len(root):],'line':frame.lineno+1}); break
   failure={'exception_type':type(call.excinfo.value).__name__,'frames':frames[-12:]}
  report.safe_failure=failure
 def pytest_runtest_logreport(self,report):
  result['reports'].append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'xfail':bool(getattr(report,'wasxfail',False)),'failure':getattr(report,'safe_failure',None)})
code=pytest.main([target,'-q','-c',str(source/'pytest.ini'),'-p','no:cacheprovider','--tb=no','--show-capture=no','--basetemp',str(fixture/'basetemp-diagnostic')],plugins=[H()])
result['return_code']=code
try:
 subprocess.run([sys.executable,'-B','-I','-c','pass'],check=True,capture_output=True)
 result['sentinel']={'status':'completed'}
except AssertionError:
 result['sentinel']={'status':'denied','exception_type':'AssertionError'}
except BaseException:
 result['sentinel']={'status':'unexpected','exception_type':type(sys.exc_info()[1]).__name__}
print(mark+json.dumps(result,sort_keys=True));raise SystemExit(0)
''' % (str(SOURCE), str(FIXTURES), node, MARK)


def all_passed(row, count):
    return (
        row["return_code"] == 0
        and not row["collection_errors"]
        and len(row["nodes"]) == count
        and len(row["reports"]) == count * 3
        and all(report["outcome"] == "passed" and not report["xfail"] for report in row["reports"])
    )


def author_red(row):
    failures = [report for report in row["reports"] if report["when"] == "call" and report["outcome"] == "failed"]
    return (
        row["return_code"] == 1
        and not row["collection_errors"]
        and len(row["nodes"]) == 1
        and len(row["reports"]) == 3
        and len(failures) == 1
        and failures[0]["failure"] is not None
        and failures[0]["failure"]["exception_type"] == "AssertionError"
        and failures[0]["failure"]["frames"][-1] == {
            "path": "fixture/clean/tests/test_author_daily_gate.py", "line": 540
        }
        and {report["when"] for report in row["reports"]} == {"setup", "call", "teardown"}
        and all(report["outcome"] == "passed" for report in row["reports"] if report["when"] != "call")
    )


def run_case(run, code, limit):
    capture, output = run.invoke(code, limit)
    require(capture["stopped_reason"] is None, "case_stopped")
    require(not any(stream["truncated"] for stream in capture["streams"].values()), "case_truncated")
    data = callback(output)
    require(capture["exit_code"] == data["return_code"], "process_callback_exit_mismatch")
    return {"capture": capture, "callback": data}


def main():
    require(not DESTINATION.exists() and not DESTINATION.is_symlink(), "existing_evidence")
    result = {"status": "failed", "phase": "preflight", "candidate_scope": "test_fixtures_only"}
    started = time.monotonic()
    try:
        require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, "start_disk_floor")
        require(sha(RUNNER) == RUNNER_SHA, "runner_drift")
        require(sha(POLICY) == POLICY_SHA, "policy_drift")
        require(sha(HELPER) == HELPER_SHA, "helper_drift")
        require(not (SOURCE / "tests" / "test_google_oauth_related_refresh_pg.py").exists(), "restricted_source_present")
        require(not (SOURCE / ".env").exists(), "dotenv_present")
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(PSUTIL))
        import psutil
        require(psutil.__version__ == "7.0.0", "psutil_version")
        run = load_runner()
        source_before = run.manifest()
        fixtures_before = fixture_hashes()
        result["input_hashes"] = {"runner": sha(RUNNER), "policy": sha(POLICY), "helper": sha(HELPER), "fixtures": fixtures_before}
        result["phase"] = "os_controls"
        control_capture, control_output = run.invoke(run.CONTROL, 30)
        result["controls"] = {"capture": control_capture, "checks": json.loads(control_output)}
        require(control_capture["exit_code"] == 0 and control_capture["stopped_reason"] is None, "os_control_failed")
        result["phase"] = "author"
        author_clean = run_case(run, author_code("clean"), 60)
        author_dirty = run_case(run, author_code("dirty"), 60)
        result["author"] = {"clean": author_clean, "dirty": author_dirty}
        require(author_red(author_clean["callback"]), "author_red_not_intended_assertion")
        require(all_passed(author_dirty["callback"], 1), "author_green_not_passed")
        result["phase"] = "diagnostic"
        diagnostic_clean = run_case(run, diagnostic_code("clean"), 60)
        diagnostic_dirty = run_case(run, diagnostic_code("dirty"), 60)
        result["diagnostic"] = {"clean": diagnostic_clean, "dirty": diagnostic_dirty}
        require(all_passed(diagnostic_clean["callback"], 4), "diagnostic_clean_class_failed")
        require(all_passed(diagnostic_dirty["callback"], 4), "diagnostic_dirty_class_failed")
        require(diagnostic_clean["callback"]["sentinel"] == {"status": "denied", "exception_type": "AssertionError"}, "diagnostic_red_sentinel")
        require(diagnostic_dirty["callback"]["sentinel"] == {"status": "completed"}, "diagnostic_green_sentinel")
        require(run.manifest() == source_before, "source_drift_after")
        require(fixture_hashes() == fixtures_before, "fixture_drift_after")
        result["source_manifest_unchanged"] = True
        result["fixture_hashes_unchanged"] = True
        result["candidate_limitations"] = [
            "diagnostic candidate does not restore original audit-hook parity for connect_ex or os.spawn* paths",
            "candidate proof does not establish aggregate-suite success or production readiness",
        ]
        result["status"] = "passed"
        result["phase"] = "finished"
    except BaseException:
        result["error_type"] = type(sys.exc_info()[1]).__name__
    finally:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["free_bytes_after"] = shutil.disk_usage(ROOT).free
        run = load_runner()
        run.put(DESTINATION, result)
    print(json.dumps({"status": result["status"], "phase": result["phase"], "duration_seconds": result["duration_seconds"]}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
