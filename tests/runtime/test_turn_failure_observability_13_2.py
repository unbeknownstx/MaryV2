from __future__ import annotations

import asyncio
from contextlib import suppress
from email.message import Message
from io import BytesIO
import json
from threading import Event
from time import sleep
from urllib.error import HTTPError

import pytest

from mary.core.config import Config
from mary.core.service import MaryCoreService
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.protocol.models import TurnRequest, TurnResponse
from mary.protocol.client import MaryClient, MaryProtocolError
from mary.protocol import client as protocol_client
from mary.runtime.turn_observability import (
    TurnTraceRecorder,
    bind_turn_trace,
    reset_turn_trace,
    trace_correlation_id,
    upstream_request_hash,
)
from mary.runtime import turn_observability
from tests.protocol.test_core_service import FakeApplication


PRIVATE_PROMPT = "private creator prompt that must never enter telemetry"
PRIVATE_MEMORY = "private memory evidence that must never enter telemetry"
PRIVATE_OUTPUT = "private provider output that must never enter telemetry"
SECRET_TOKEN = "test-secret-that-must-never-enter-telemetry"


class TimeoutProvider(LLMInterface):
    def __init__(self, name: str) -> None:
        self.name = name

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        raise TimeoutError(f"{PRIVATE_PROMPT} {SECRET_TOKEN}")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return self.name

    def model_name(self) -> str:
        return "timeout-model"


class SuccessProvider(LLMInterface):
    def __init__(self, name: str) -> None:
        self.name = name

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        return LLMResponse(
            content=PRIVATE_OUTPUT,
            provider=self.name,
            model="success-model",
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return self.name

    def model_name(self) -> str:
        return "success-model"


def _recorder(request_id: str = "req-observability") -> TurnTraceRecorder:
    return TurnTraceRecorder(
        request_id=request_id,
        core_instance_id="core-observability",
        core_uptime_ms=lambda: 1250.0,
    )


def _trace_json(trace: TurnTraceRecorder) -> str:
    return json.dumps(trace.snapshot(), sort_keys=True)


def _assert_private_content_absent(value: str) -> None:
    assert PRIVATE_PROMPT not in value
    assert PRIVATE_MEMORY not in value
    assert PRIVATE_OUTPUT not in value
    assert SECRET_TOKEN not in value


def test_trace_is_bounded_allowlisted_and_rejects_prose_request_ids(monkeypatch):
    emitted: list[str] = []
    monkeypatch.setattr(turn_observability._LOGGER, "info", emitted.append)
    trace = _recorder(f"{PRIVATE_PROMPT} {SECRET_TOKEN}")

    with pytest.raises(RuntimeError):
        with trace.stage(
            "dialogue_persistence",
            failure_kind="post_processing_failure",
        ):
            raise RuntimeError(f"{PRIVATE_MEMORY} {PRIVATE_OUTPUT}")

    for index in range(100):
        trace.record(
            "provider_generation",
            status="success",
            elapsed_ms=float(index),
            provider="safe-provider",
            attempt=1,
        )
    final = trace.finish(
        outcome="failure",
        failure_kind="post_processing_failure",
        error=RuntimeError(PRIVATE_PROMPT),
    )

    assert trace.request_id.startswith("request_")
    assert len(final["stages"]) == 64
    assert final["dropped_stage_count"] == 37
    assert len(emitted) == 65
    assert sum('"event":"mary.turn.stage"' in item for item in emitted) == 64
    assert sum('"event":"mary.turn.complete"' in item for item in emitted) == 1
    assert final["failure_kind"] == "post_processing_failure"
    assert final["error_type"] == "RuntimeError"
    _assert_private_content_absent(json.dumps(final, sort_keys=True))


def test_provider_timeout_and_successful_fallback_are_distinguishable_and_sanitized():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    router = LLMRouter(config)
    router.register_provider("primary", TimeoutProvider("primary"))
    router.register_provider("secondary", SuccessProvider("secondary"))
    trace = _recorder()
    token = bind_turn_trace(trace)
    try:
        response = router.generate([
            LLMMessage(role="user", content=PRIVATE_PROMPT),
        ])
        trace.finish(outcome="success")
    finally:
        reset_turn_trace(token)

    assert response.provider == "secondary"
    stages = trace.snapshot()["stages"]
    timeout = next(
        item
        for item in stages
        if item["stage"] == "provider_generation"
        and item["provider"] == "primary"
    )
    assert timeout["status"] == "failure"
    assert timeout["failure_kind"] == "provider_timeout"
    assert timeout["error_type"] == "TimeoutError"
    fallback = next(
        item
        for item in stages
        if item["stage"] == "provider_fallback"
        and item.get("provider") == "primary"
    )
    assert fallback["status"] == "success"
    assert fallback["outcome"] == "provider_timeout"
    assert any(
        item["stage"] == "provider_generation"
        and item.get("provider") == "secondary"
        and item["status"] == "success"
        for item in stages
    )
    _assert_private_content_absent(_trace_json(trace))


def test_finished_trace_rejects_late_worker_stages():
    trace = _recorder()
    trace.record("core_ingress", status="success", elapsed_ms=1)
    finished = trace.finish(
        outcome="failure",
        failure_kind="upstream_disconnect",
    )
    assert trace.record(
        "application_turn",
        status="success",
        elapsed_ms=1,
    ) == {}
    assert trace.snapshot()["stages"] == finished["stages"]


def test_total_elapsed_time_is_bounded():
    trace = _recorder()
    trace.started -= 100_000_000.0
    finished = trace.finish(outcome="success")
    assert finished["total_elapsed_ms"] == 86_400_000.0


def test_trace_links_conversation_and_allowlists_result_ids():
    trace = _recorder()
    trace.set_turn_id("turn-safe")
    trace.set_conversation_id("conversation-safe")
    event = trace.record(
        "attention_publication",
        status="success",
        elapsed_ms=1,
        outcome="published",
        result_ids={
            "attention_id": "attention-safe",
            "experience_id": ["experience-1", "unsafe private id"],
            "unknown_id": "must-not-appear",
            "memory_object_id": PRIVATE_MEMORY,
        },
    )
    assert event["conversation_id"] == trace_correlation_id(
        "conversation-safe",
        prefix="conversation",
    )
    assert event["result_ids"] == {
        "attention_id": "attention-safe",
        "experience_id": ["experience-1"],
    }
    _assert_private_content_absent(json.dumps(event, sort_keys=True))


def test_client_preserves_only_safe_core_request_id_on_http_failure(monkeypatch):
    headers = Message()
    headers["X-Mary-Request-ID"] = "request_safe_failure"

    def fail_request(*_args, **_kwargs):
        raise HTTPError(
            "https://core.example/v1/turn",
            500,
            "private upstream detail",
            headers,
            BytesIO(f"{PRIVATE_OUTPUT} {SECRET_TOKEN}".encode()),
        )

    monkeypatch.setattr(protocol_client, "urlopen", fail_request)
    client = MaryClient(
        "https://core.example",
        token="secret",
        device_id="mobile",
        surface="mobile",
    )
    with pytest.raises(MaryProtocolError) as caught:
        client.turn(PRIVATE_PROMPT)

    assert caught.value.request_id == "request_safe_failure"
    assert caught.value.status_code == 500
    serialized = str(caught.value)
    assert "request_safe_failure" in serialized
    _assert_private_content_absent(serialized)


def test_provider_exhaustion_has_a_distinct_terminal_fallback_failure():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = []
    router = LLMRouter(config)
    router.register_provider("primary", TimeoutProvider("primary"))
    trace = _recorder()
    token = bind_turn_trace(trace)
    try:
        with pytest.raises(RuntimeError):
            router.generate([
                LLMMessage(role="user", content=PRIVATE_PROMPT),
            ])
        trace.finish(outcome="failure", failure_kind="provider_exhausted")
    finally:
        reset_turn_trace(token)

    terminal = [
        item
        for item in trace.snapshot()["stages"]
        if item["stage"] == "provider_fallback"
        and item["status"] == "failure"
    ]
    assert len(terminal) == 1
    assert terminal[0]["failure_kind"] == "provider_exhausted"
    assert terminal[0]["outcome"] == "exhausted"
    _assert_private_content_absent(_trace_json(trace))


def test_turn_lock_wait_is_measured_without_changing_lock_scope():
    class DelayedLock:
        def acquire(self):
            sleep(0.02)
            return True

        def release(self):
            return None

    core = MaryCoreService(FakeApplication(), instance_id="lock-core")
    core.register_creator_surface({"surface_id": "test-creator"})
    core._turn_lock = DelayedLock()
    trace = _recorder()
    token = bind_turn_trace(trace)
    try:
        response = core.process_turn(TurnRequest.from_dict({"text": "hello"}))
    finally:
        reset_turn_trace(token)

    assert response.response == "hi"
    lock_stage = next(
        item
        for item in trace.snapshot()["stages"]
        if item["stage"] == "turn_lock_acquisition"
    )
    assert lock_stage["status"] == "success"
    assert lock_stage["elapsed_ms"] >= 10.0


def test_http_turn_correlates_request_and_keeps_failure_responses_sanitized(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    del fastapi
    from fastapi.testclient import TestClient
    from mary.protocol.server import create_app

    monkeypatch.setenv("MARY_CORE_TOKEN", SECRET_TOKEN)
    core = MaryCoreService(FakeApplication(), instance_id="http-core")
    core.register_creator_surface({"surface_id": "test-creator"})
    with TestClient(create_app(core)) as client:
        response = client.post(
            "/v1/turn",
            headers={
                "Authorization": f"Bearer {SECRET_TOKEN}",
                "X-Request-ID": "railway-safe-request-123",
            },
            json={"text": PRIVATE_PROMPT},
        )

    assert response.status_code == 200
    mary_request_id = response.headers["X-Mary-Request-ID"]
    assert mary_request_id.startswith("request_")
    assert response.json()["request_id"] == mary_request_id
    trace = core.recent_turn_traces()[-1]
    assert trace["request_id"] == mary_request_id
    assert trace["upstream_request_hash"] == upstream_request_hash(
        "railway-safe-request-123"
    )
    assert trace["core_instance_id"] == "http-core"
    assert trace["core_uptime_ms"] >= 0.0
    assert trace["outcome"] == "success"
    assert {
        "core_ingress",
        "turn_lock_acquisition",
        "application_turn",
        "response_serialization",
    }.issubset({item["stage"] for item in trace["stages"]})
    _assert_private_content_absent(json.dumps(trace, sort_keys=True))


def test_authenticated_trace_query_filters_ids_and_marks_replay(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    del fastapi
    from fastapi.testclient import TestClient
    from mary.protocol.server import create_app

    monkeypatch.setenv("MARY_CORE_TOKEN", SECRET_TOKEN)
    core = MaryCoreService(FakeApplication(), instance_id="query-core")
    core.register_creator_surface({"surface_id": "test-creator"})
    headers = {"Authorization": f"Bearer {SECRET_TOKEN}"}
    payload = {
        "text": "hello",
        "turn_id": "turn-query-safe",
        "conversation_id": "conversation-query-safe",
    }
    with TestClient(create_app(core)) as client:
        first = client.post("/v1/turn", headers=headers, json=payload)
        replay = client.post("/v1/turn", headers=headers, json=payload)
        unauthorized = client.get("/v1/turn-traces")
        queried = client.get(
            "/v1/turn-traces?turn_id=turn-query-safe&limit=1000",
            headers=headers,
        )
        unsafe = client.get(
            "/v1/turn-traces?request_id=private%20request",
            headers=headers,
        )

    assert first.status_code == replay.status_code == 200
    assert first.json()["request_id"] != replay.json()["request_id"]
    assert unauthorized.status_code == 401
    assert unsafe.status_code == 200
    assert unsafe.json()["count"] == 0
    body = queried.json()
    assert body["limit"] == 40
    assert [trace["outcome"] for trace in body["traces"]] == [
        "replayed",
        "success",
    ]
    assert all(
        trace["conversation_id"] == trace_correlation_id(
            "conversation-query-safe",
            prefix="conversation",
        )
        for trace in body["traces"]
    )
    assert "conversation-query-safe" not in json.dumps(body, sort_keys=True)
    assert any(
        stage["status"] == "skipped"
        and stage.get("outcome") == "replayed"
        for stage in body["traces"][0]["stages"]
    )


def test_health_stays_responsive_and_cancelled_request_records_upstream_disconnect(
    monkeypatch,
):
    fastapi = pytest.importorskip("fastapi")
    httpx = pytest.importorskip("httpx")
    del fastapi
    from mary.protocol.server import create_app

    class BlockingApplication(FakeApplication):
        def __init__(self):
            super().__init__()
            self.started = Event()
            self.release = Event()

        def run(self, text, metadata=None):
            self.started.set()
            assert self.release.wait(timeout=2)
            return super().run(text, metadata=metadata)

    application = BlockingApplication()
    core = MaryCoreService(application, instance_id="disconnect-core")
    core.register_creator_surface({"surface_id": "test-creator"})
    monkeypatch.setenv("MARY_CORE_TOKEN", SECRET_TOKEN)
    app = create_app(core)

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            turn_task = asyncio.create_task(
                client.post(
                    "/v1/turn",
                    headers={
                        "Authorization": f"Bearer {SECRET_TOKEN}",
                        "X-Request-ID": "upstream-disconnect-test",
                    },
                    json={"text": PRIVATE_PROMPT},
                )
            )
            deadline = asyncio.get_running_loop().time() + 1
            while (
                not application.started.is_set()
                and asyncio.get_running_loop().time() < deadline
            ):
                await asyncio.sleep(0.005)
            assert application.started.is_set()

            health = await client.get("/v1/health")
            assert health.status_code == 200
            assert health.json()["ok"] is True

            turn_task.cancel()
            with suppress(asyncio.CancelledError):
                await turn_task
            trace = core.recent_turn_traces()[-1]
            retained_stage_count = len(trace["stages"])
            application.release.set()
            await asyncio.sleep(0.05)
            await asyncio.to_thread(core.close)
            return trace, retained_stage_count

    trace, retained_stage_count = asyncio.run(exercise())
    assert trace["failure_kind"] == "upstream_disconnect"
    assert trace["error_type"] == "CancelledError"
    assert trace["upstream_request_hash"] == upstream_request_hash(
        "upstream-disconnect-test"
    )
    assert len(trace["stages"]) == retained_stage_count
    _assert_private_content_absent(json.dumps(trace, sort_keys=True))


def test_serialization_failure_returns_request_id_and_records_safe_failure(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    del fastapi
    from fastapi.testclient import TestClient
    from mary.protocol.server import create_app

    monkeypatch.setenv("MARY_CORE_TOKEN", SECRET_TOKEN)
    core = MaryCoreService(FakeApplication(), instance_id="serialization-core")
    core.register_creator_surface({"surface_id": "test-creator"})

    def fail_serialization(self):
        raise RuntimeError(f"{PRIVATE_OUTPUT} {SECRET_TOKEN}")

    monkeypatch.setattr(TurnResponse, "to_dict", fail_serialization)
    with TestClient(create_app(core)) as client:
        response = client.post(
            "/v1/turn",
            headers={
                "Authorization": f"Bearer {SECRET_TOKEN}",
                "X-Request-ID": "serialization-request",
            },
            json={"text": PRIVATE_PROMPT},
        )

    assert response.status_code == 500
    mary_request_id = response.headers["X-Mary-Request-ID"]
    assert mary_request_id.startswith("request_")
    assert response.json()["detail"] == "Mary Core response serialization failed."
    trace = core.recent_turn_traces()[-1]
    assert trace["failed_stage"] == "response_serialization"
    assert trace["failure_kind"] == "serialization_failure"
    _assert_private_content_absent(json.dumps(trace, sort_keys=True))


def test_secret_shaped_upstream_id_and_application_error_are_never_reflected(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    del fastapi
    from fastapi.testclient import TestClient
    from mary.protocol.server import create_app

    class FailingApplication(FakeApplication):
        def run(self, text, metadata=None):
            raise RuntimeError(
                f"{PRIVATE_PROMPT} {PRIVATE_MEMORY} {PRIVATE_OUTPUT} {SECRET_TOKEN}"
            )

    upstream_request_id = "sk_live_abcdefghijklmnopqrstuvwxyz123456"
    monkeypatch.setenv("MARY_CORE_TOKEN", SECRET_TOKEN)
    core = MaryCoreService(FailingApplication(), instance_id="failure-core")
    with TestClient(create_app(core)) as client:
        response = client.post(
            "/v1/turn",
            headers={
                "Authorization": f"Bearer {SECRET_TOKEN}",
                "X-Request-ID": upstream_request_id,
            },
            json={"text": PRIVATE_PROMPT},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Mary Core turn failed."
    assert response.headers["X-Mary-Request-ID"].startswith("request_")
    trace = core.recent_turn_traces()[-1]
    assert trace["failure_kind"] == "application_exception"
    assert trace["upstream_request_hash"] == upstream_request_hash(
        upstream_request_id
    )
    serialized = json.dumps(trace, sort_keys=True)
    assert upstream_request_id not in serialized
    _assert_private_content_absent(serialized)