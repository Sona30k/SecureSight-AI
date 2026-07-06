from collections import Counter

from app.services.demo_graph import ENTITY_COUNTS, build_fraud_graph


def test_faker_graph_has_520_unique_typed_entities_and_connected_relationships():
    events = build_fraud_graph()
    entities = {
        (event[f"{side}_type"], event[f"{side}_value"])
        for event in events
        for side in ("source", "target")
    }
    counts = Counter(kind for kind, _ in entities)

    assert len(entities) == 520
    assert counts == ENTITY_COUNTS
    assert len(events) >= 800
    assert all(event["attributes"]["synthetic"] is True for event in events)
    assert len({event["event_hash"] for event in events}) == len(events)
