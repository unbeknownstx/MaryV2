from mary.governance.limits import RuntimeLimits
from mary.knowledge.concepts import Concept
from mary.learning.experiments import ExperimentManager
from mary.personality.preference_promotion import PreferencePromotionSystem


def test_single_knowledge_concept_cannot_grow_unbounded():
    concept = Concept(id="concept_1", name="bounded", statement="test")

    for index in range(300):
        concept.add_source(f"source_{index}")
        concept.add_tag(f"tag_{index}")
        concept.add_alias(f"alias_{index}")
        concept.add_evidence(
            "evidence " + ("x" * 5000),
            confidence=0.8,
            metadata={"payload": ["x" * 5000] * 100},
        )
        concept.add_relation(
            "related_to",
            f"concept_{index + 2}",
            metadata={"payload": ["y" * 5000] * 100},
        )

    assert len(concept.source_ids) <= concept.MAX_SOURCES
    assert len(concept.tags) <= concept.MAX_TAGS
    assert len(concept.aliases) <= concept.MAX_ALIASES
    assert len(concept.evidence) <= concept.MAX_EVIDENCE
    assert len(concept.relations) <= concept.MAX_RELATIONS
    assert max(len(item.statement) for item in concept.evidence) <= concept.MAX_TEXT


def test_preference_evidence_and_history_are_bounded():
    limits = RuntimeLimits(
        knowledge_candidate_capacity=32,
        learning_event_capacity=64,
        process_text_characters=256,
    )
    system = PreferencePromotionSystem(limits=limits)

    for index in range(100):
        name = f"candidate_{index}"
        for observation in range(50):
            system.observe(
                name,
                strength=0.8,
                confidence=0.9,
                reason="r" * 1000,
                evidence_id=f"{index}_{observation}",
            )

    assert len(system.candidates) <= system.candidate_capacity
    assert all(
        len(candidate.get("observations", [])) <= system.observation_capacity
        for candidate in system.candidates.values()
    )

    # Drive explicit decisions into the bounded history ledger.
    for name in list(system.candidates):
        system.reject(name, reason="not now")
    for index in range(100, 200):
        name = f"candidate_{index}"
        system.observe(name, strength=0.8, confidence=0.9, evidence_id=str(index))
        system.reject(name, reason="not now")

    assert len(system.history) <= system.history_capacity


def test_experiment_manager_bounds_records_and_per_experiment_details():
    limits = RuntimeLimits(
        experiment_capacity=8,
        experiment_observation_capacity=5,
        process_text_characters=128,
    )
    manager = ExperimentManager(limits=limits)

    for index in range(20):
        experiment = manager.create(
            "title " + ("x" * 500),
            "hypothesis " + ("x" * 500),
            "outcome " + ("x" * 500),
            metadata={"huge": ["z" * 1000] * 100},
        )
        for observation in range(20):
            manager.add_observation(experiment.id, f"observation-{observation}-" + ("x" * 500))
            manager.add_lesson(experiment.id, f"lesson-{observation}-" + ("y" * 500))

    assert len(manager.experiments) <= limits.experiment_capacity
    for experiment in manager.experiments:
        assert len(experiment.observations) <= limits.experiment_observation_capacity
        assert len(experiment.lessons) <= limits.experiment_observation_capacity
        assert len(experiment.title) <= limits.process_text_characters
        assert len(experiment.hypothesis) <= limits.process_text_characters
        assert len(experiment.expected_outcome) <= limits.process_text_characters
