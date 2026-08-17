from scripts.load_test_web_tracking import _latency_report, _status_counts


def test_latency_report_handles_empty_and_percentiles():
    assert _latency_report([]) == {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    results = [(202, float(value)) for value in range(1, 101)]
    report = _latency_report(results)

    assert report["mean"] == 50.5
    assert report["p50"] == 50.0
    assert report["p95"] == 95.0
    assert report["p99"] == 99.0
    assert report["max"] == 100.0


def test_status_counts_keeps_network_failures_separate():
    assert _status_counts([(202, 10), (202, 20), (400, 5), (0, 5000)]) == {
        "202": 2,
        "400": 1,
        "0": 1,
    }
