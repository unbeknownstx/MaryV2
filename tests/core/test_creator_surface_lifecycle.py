from threading import RLock, Thread
from time import monotonic, sleep

import pytest

from mary.autonomy.runtime import AutonomyRuntimeStatus
from mary.core.creator_surface import CreatorSurfaceCoordinator
from mary.core.service import MaryCoreService


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_surface_leases_drive_active_idle_sleeping_without_heartbeat_activity():
    clock = FakeClock()
    lifecycle = CreatorSurfaceCoordinator(
        idle_seconds=5,
        sleep_seconds=10,
        lease_ttl_seconds=30,
        clock=clock,
    )

    assert lifecycle.status()["state"] == "SLEEPING"
    assert lifecycle.register("browser")["state"] == "ACTIVE"

    clock.advance(5)
    assert lifecycle.status()["state"] == "IDLE"
    lifecycle.renew("browser", activity=False)
    clock.advance(5)
    assert lifecycle.status()["state"] == "SLEEPING"

    assert lifecycle.wake("browser")["state"] == "ACTIVE"
    lifecycle.renew("browser", visible=False, foreground=False)
    clock.advance(5)
    assert lifecycle.status()["state"] == "IDLE"


def test_zero_or_expired_leases_sleep_and_multiple_surfaces_are_independent():
    clock = FakeClock()
    lifecycle = CreatorSurfaceCoordinator(
        idle_seconds=2,
        sleep_seconds=8,
        lease_ttl_seconds=4,
        clock=clock,
    )
    lifecycle.register("browser")
    lifecycle.register("phone")
    assert lifecycle.disconnect("browser")["surface_count"] == 1
    assert lifecycle.disconnect("phone")["state"] == "SLEEPING"

    lifecycle.register("phone")
    clock.advance(4)
    status = lifecycle.status()
    assert status["state"] == "SLEEPING"
    assert status["surface_count"] == 0


def test_offline_is_explicit_and_cannot_be_cleared_by_presence_or_wake():
    lifecycle = CreatorSurfaceCoordinator()
    lifecycle.register("phone")
    assert lifecycle.set_offline(True)["state"] == "OFFLINE"
    assert lifecycle.register("browser")["state"] == "OFFLINE"
    assert lifecycle.renew("phone", activity=True)["state"] == "OFFLINE"
    with pytest.raises(RuntimeError, match="explicitly offline"):
        lifecycle.wake("phone")

    assert lifecycle.set_offline(False)["state"] == "ACTIVE"
    assert lifecycle.wake("phone")["state"] == "ACTIVE"


def test_surface_registry_is_bounded():
    lifecycle = CreatorSurfaceCoordinator(max_surfaces=2)
    lifecycle.register("one")
    lifecycle.register("two")
    with pytest.raises(RuntimeError, match="limit"):
        lifecycle.register("three")


class FakeRegistry:
    def __init__(self) -> None:
        self.lifecycle_lock = RLock()

    def is_live(self, _node_id: str) -> bool:
        return False


class PolicyOwner:
    def set_execution_policy(self, policy) -> None:
        self.policy = policy


class FakeAutonomy:
    def __init__(self) -> None:
        self.status = AutonomyRuntimeStatus.RUNNING
        self.pause_count = 0
        self.resume_count = 0

    def pause(self) -> None:
        self.pause_count += 1
        self.status = AutonomyRuntimeStatus.PAUSED

    def resume(self) -> None:
        self.resume_count += 1
        self.status = AutonomyRuntimeStatus.RUNNING


class FakeMary:
    def __init__(self) -> None:
        self.node_registry = FakeRegistry()
        self.llm = PolicyOwner()
        self.tools = PolicyOwner()
        self.autonomy = FakeAutonomy()


class FakeApplication:
    def __init__(self) -> None:
        self.mary = FakeMary()
        self.run_count = 0

    def run(self, *_args, **_kwargs):
        self.run_count += 1
        raise AssertionError("A sleeping turn must not reach the application.")

    def close(self):
        return True


def test_core_owns_one_ephemeral_lifecycle_and_only_resumes_its_pause():
    clock = FakeClock()
    coordinator = CreatorSurfaceCoordinator(
        idle_seconds=5,
        sleep_seconds=10,
        lease_ttl_seconds=30,
        clock=clock,
    )
    application = FakeApplication()
    service = MaryCoreService(
        application=application,
        creator_surface_coordinator=coordinator,
    )

    assert service.application is application
    assert service.mary is application.mary
    assert service.health()["ok"] is True
    assert service.creator_lifecycle_status()["state"] == "SLEEPING"
    assert application.mary.autonomy.pause_count == 1

    with pytest.raises(RuntimeError, match="sleeping or offline"):
        service.process_turn({"text": "blocked"})
    with pytest.raises(RuntimeError, match="sleeping or offline"):
        service._presence_pulse({}, device_id="test-creator")
    assert application.run_count == 0

    service.register_creator_surface({"surface_id": "browser"})
    assert application.mary.autonomy.resume_count == 1
    service.set_creator_offline(True)
    assert application.mary.autonomy.pause_count == 2
    with pytest.raises(RuntimeError, match="sleeping or offline"):
        service.runtime_action(
            {"action": "presence.idle_tick", "args": {}, "device_id": "browser"}
        )
    service.register_creator_surface({"surface_id": "phone"})
    assert service.creator_lifecycle_status()["state"] == "OFFLINE"
    assert application.mary.autonomy.resume_count == 1
    service.set_creator_offline(False)
    assert application.mary.autonomy.resume_count == 2


def test_core_timer_sleeps_without_request_and_serializes_concurrent_transitions():
    coordinator = CreatorSurfaceCoordinator(
        idle_seconds=0.03,
        sleep_seconds=0.06,
        lease_ttl_seconds=0.2,
    )
    application = FakeApplication()
    service = MaryCoreService(
        application=application,
        creator_surface_coordinator=coordinator,
    )
    service.register_creator_surface({"surface_id": "browser"})

    deadline = monotonic() + 1.0
    while application.mary.autonomy.pause_count < 2 and monotonic() < deadline:
        sleep(0.01)

    # No lifecycle status or execution call was needed to trigger this pause.
    assert application.mary.autonomy.pause_count == 2
    assert application.mary.autonomy.status == AutonomyRuntimeStatus.PAUSED

    service.wake_creator_surfaces({"surface_id": "browser"})
    assert application.mary.autonomy.resume_count == 2

    workers = [
        Thread(target=service.set_creator_offline, args=(True,))
        for _ in range(8)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=1)

    assert all(not worker.is_alive() for worker in workers)
    assert application.mary.autonomy.pause_count == 3
    assert service.creator_lifecycle_status()["state"] == "OFFLINE"
    service.close()


def test_service_responses_preserve_independent_surface_ids():
    application = FakeApplication()
    application.mary.autonomy.status = AutonomyRuntimeStatus.STOPPED
    service = MaryCoreService(application=application)

    first = service.register_creator_surface({"surface_id": "tab-one"})
    second = service.register_creator_surface({"surface_id": "tab-two"})
    assert first["surface_id"] == "tab-one"
    assert second["surface_id"] == "tab-two"
    disconnected = service.disconnect_creator_surface({"surface_id": "tab-one"})
    assert disconnected["surface_id"] == "tab-one"
    assert disconnected["surface_count"] == 1
    assert disconnected["surfaces"][0]["surface_id"] == "tab-two"
    service.close()