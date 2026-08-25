from app.observability import MetricsRegistry


def test_metrics_summary_is_bounded_and_aggregated():
    metrics = MetricsRegistry()
    metrics.observe("tool", 10)
    metrics.observe("tool", 20)
    summary = metrics.summary("tool")
    assert summary.count == 2
    assert summary.average_ms == 15
    assert summary.maximum_ms == 20
    assert summary.p50_ms == 10
    assert summary.p95_ms == 20


def test_metrics_counters_are_separate_from_duration_samples():
    metrics = MetricsRegistry()
    metrics.increment("route.fast")
    metrics.increment("route.fast", 2)
    assert metrics.count("route.fast") == 3
