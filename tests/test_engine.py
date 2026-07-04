def _status(store, bid):
    return {s["node_id"]: s["status"] for s in store.get_node_states(bid)}


def test_marking_is_confirm_only_and_and_joins(engine, store, recipe):
    bid = engine.create_bake(recipe, name="t")
    s = _status(store, bid)
    # START's successors are ready; everything downstream blocked
    assert s["feed_levain"] == "ready" and s["autolyse"] == "ready"
    assert s["mix"] == "blocked"

    engine.begin(bid, "feed_levain")
    engine.done(bid, "feed_levain")
    # AND-join: mix needs BOTH levain and autolyse
    assert _status(store, bid)["mix"] == "blocked"

    engine.begin(bid, "autolyse")
    engine.done(bid, "autolyse")
    assert _status(store, bid)["mix"] == "ready"
    # nothing auto-advanced past the newly-ready node
    assert _status(store, bid)["bulk_fold_1"] == "blocked"


def test_capture_tags_elapsed(engine, store, recipe, tmp_path):
    bid = engine.create_bake(recipe, name="t")
    engine.begin(bid, "feed_levain")
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake")
    engine.capture(bid, "feed_levain", img, tags=["fed"])
    media = store.get_media(bake_id=bid, node_id="feed_levain")
    assert len(media) == 1
    assert media[0]["kind"] == "image"
