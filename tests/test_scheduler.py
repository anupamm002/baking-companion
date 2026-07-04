from datetime import timedelta

from baking_companion.scheduler import compute_schedule


def test_levain_override_and_prep_alerts(engine, store, recipe):
    bid = engine.create_bake(recipe, name="t")
    engine.begin(bid, "feed_levain", expected=timedelta(hours=2))
    sched = compute_schedule(recipe, store.get_node_states(bid))
    span = sched["finish"]["feed_levain"] - sched["now"]
    assert abs(span - timedelta(hours=2)).total_seconds() < 120

    alert_nodes = {s["node"] for s in sched["suggestions"]}
    assert "preheat" in alert_nodes
    assert "pull_and_score" in alert_nodes
    # preheat is scheduled to start before the bake, not "now"
    preheat = next(s for s in sched["suggestions"] if s["node"] == "preheat")
    assert preheat["when"] > sched["now"]
