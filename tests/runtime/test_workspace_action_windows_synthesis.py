from mary.runtime.workspace_context import build_workspace_context


def test_workspace_context_exposes_current_high_level_actions_without_execution_claim():
    context = build_workspace_context({
        "action_windows": {
            "windows": [{
                "window_id": "w1",
                "surface": "game",
                "context": "dialog choice",
                "revision": 3,
                "actions": [{"name": "choose_left", "description": "Choose left", "capability": "game.choice", "disposable": True}],
            }]
        }
    })
    assert context["action_windows"][0]["actions"][0]["name"] == "choose_left"
    assert "authorization" in context["guidance"].lower()
