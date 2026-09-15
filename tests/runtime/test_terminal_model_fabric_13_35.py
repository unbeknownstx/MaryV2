from mary.runtime import terminal


class _Gateway:
    def state(self):
        return {
            "compute_fabric": {
                "model_execution": {
                    "version": "13.35",
                    "authority": "planning_and_observability_only",
                    "promotion_policy": {
                        "reachable_is_not_preferred": True,
                    },
                }
            }
        }

    def conversation(self):
        return {}

    def dashboard(self):
        return {}

    def workspace(self):
        return {}


def test_remote_model_fabric_command_surfaces_suitability_policy():
    rendered = terminal._remote_command(_Gateway(), "/model-fabric", None)

    assert rendered is not None
    assert '"version": "13.35"' in rendered
    assert '"reachable_is_not_preferred": true' in rendered
    assert "planning_and_observability_only" in rendered
