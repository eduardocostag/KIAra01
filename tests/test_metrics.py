from app.observability import MetricsRegistry


def test_metrics_summary_is_bounded_and_aggregated():
    metrics = MetricsRegistry()
    metrics.observe("tool", 10)
    metrics.observe("tool", 20)
    summary = metrics.summary("tool")
    assert summary.count == 2
    assert summary.average_ms == 15
    assert summary.maximum_ms == 20
