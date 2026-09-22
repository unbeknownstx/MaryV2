from types import SimpleNamespace

from mary.cognition.self_introspection import SelfIntrospection


class _StatusOwner:
    def __init__(self, payload):
        self.payload = payload

    def status(self):
        return dict(self.payload)


class _Skill:
    def __init__(self, skill_id, name, required_capabilities=("demo.cap",), version=1):
        self.id = skill_id
        self.name = name
        self.required_capabilities = required_capabilities
        self.version = version


class _Skills(_StatusOwner):
    def __init__(self):
        super().__init__({"approved": 2, "candidates": 0, "revision_attention": 1})

    def approved(self):
        return [
            _Skill("skill-good", "Reliable Search"),
            _Skill("skill-degrading", "Old Search"),
        ]

    def revision_queue(self, limit=200):
        return [{"skill_id": "skill-degrading", "revision_pressure": 0.7}]

    def revision_lineage(self, limit=100, competence=None):
        return {"rows": []}

    def revision_review_history(self, limit=100):
        return {"decisions": 0}

    def revision_adoption_evidence(self, limit=100):
        return {"rows": [], "with_outcomes": 0, "attention_required": 0}


class _Competence:
    def status(self):
        return {"records": 8}

    def find(self, limit=500):
        return [SimpleNamespace(capability="demo.cap")]

    def summary_for(self, capability, node_ids=(), limit=4):
        return [{
            "node_id": "node-1",
            "skill_id": "skill-good",
            "attempts": 4,
            "verified_successes": 4,
            "reliability": 1.0,
            "evidence_strength": 0.8,
        }]

    def skill_summary(self, skill_id, capability="", node_ids=()):
        if skill_id == "skill-good":
            return {
                "attempts": 4,
                "successes": 4,
                "failures": 0,
                "verified_successes": 4,
                "reliability": 1.0,
                "evidence_strength": 0.8,
                "demonstrated": True,
            }
        return {
            "attempts": 4,
            "successes": 1,
            "failures": 3,
            "verified_successes": 1,
            "reliability": 0.25,
            "evidence_strength": 0.5,
            "demonstrated": True,
        }


class _Models:
    def snapshot(self):
        return {
            "count": 1,
            "trial_ready": 0,
            "records": [{
                "id": "exp-1",
                "candidate_id": "mary-lora-v1",
                "status": "reviewed",
                "benchmark_verified": False,
                "trial_ready": False,
                "missing_scores": ["character"],
                "failed_scores": [],
            }],
        }


class _NodeRegistry:
    def snapshot(self):
        return {
            "registered": 1,
            "nodes": [{
                "node_id": "node-1",
                "connected": True,
                "capabilities": {
                    "demo.cap": {
                        "available": True,
                        "readiness": "ready",
                        "metadata": {"execution_authorized": False},
                    }
                },
            }],
        }


class _Identity:
    purpose = "test"
    creator = "creator"


class _SelfModel:
    def profile(self):
        return {}


class _UserModel:
    name = "creator"

    def get_identity(self):
        return {}


class _Directives:
    def get_active(self):
        return []


class _Empty:
    def status(self):
        return {}


class _Emotion:
    def snapshot(self):
        return {"primary": "neutral", "intensity": 0.0}


def _subject():
    return SelfIntrospection(
        identity=_Identity(),
        self_model=_SelfModel(),
        biography=SimpleNamespace(),
        personality=SimpleNamespace(),
        values=SimpleNamespace(),
        preferences=SimpleNamespace(),
        character=SimpleNamespace(),
        user_model=_UserModel(),
        creator_directives=_Directives(),
        agency=_Empty(),
        autonomy=SimpleNamespace(),
        tools=_StatusOwner({}),
        emotion=_Emotion(),
        node_registry=_NodeRegistry(),
        competence=_Competence(),
        knowledge_fabric=_Empty(),
        procedural_skills=_Skills(),
        world_model=_Empty(),
        model_experiments=_Models(),
    )


def test_self_model_evidence_query_explains_demonstrated_degrading_and_experimental_states():
    result = _subject().build(
        "capabilities",
        "What have you demonstrated, what is degrading, and which models are experimental?",
    )
    answer = result["fallback_response"]

    assert "demonstrated approved procedure" in answer
    assert "degrading procedure" in answer
    assert "experimental model record" in answer
    assert "permission, availability, competence, and production promotion remain separate" in answer
    assert "Old Search" in answer
    assert "mary-lora-v1" in answer


def test_generic_capability_question_does_not_invent_self_evidence_summary():
    result = _subject().build("capabilities", "Can you use the web?")
    answer = result["fallback_response"]

    assert "My current self-evidence distinguishes" not in answer
