from mary.knowledge import WorldContextItem, WorldContextStore


def test_world_context_is_ephemeral_and_retrievable():
    world = WorldContextStore()
    world.ingest(
        WorldContextItem(
            topic="new anime trailer",
            summary="A new trailer is trending among anime fans",
            source="example-source",
            lane="anime",
            confidence=.8,
        )
    )
    assert world.relevant("anime trailer")[0].lane == "anime"
    status = world.snapshot()
    assert status["authority"] == "ephemeral_external_context_only"
