"""ASGI/HTTP/WebSocket transport for the MaryV2 13.2 unified core."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
import secrets
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
except ImportError:  # pragma: no cover - handled by create_app/run_server
    FastAPI = HTTPException = Request = WebSocket = WebSocketDisconnect = None

from mary.core.service import MaryCoreService
from mary.protocol.models import (
    CapabilityRouteRequest,
    CapabilityTaskPreviewRequest,
    NodeHeartbeatRequest,
    NodeRegistrationRequest,
    RuntimeActionRequest,
    TurnRequest,
    WorkspaceActionRequest,
)


def _token() -> str:
    return os.getenv("MARY_CORE_TOKEN", "").strip()


def _authorized(value: str | None) -> bool:
    expected = _token()
    if not expected:
        return os.getenv("MARY_CORE_ALLOW_INSECURE_LOCAL", "").strip().lower() in {"1", "true", "yes", "on"}
    supplied = str(value or "")
    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()
    return bool(supplied) and secrets.compare_digest(supplied, expected)


def create_app(service: MaryCoreService | None = None):
    if FastAPI is None:  # pragma: no cover - installation guidance
        raise RuntimeError("Mary Core HTTP transport requires `pip install fastapi uvicorn`.")

    core = service or MaryCoreService()

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            await asyncio.to_thread(core.close)

    app = FastAPI(title="MaryV2 Core", version="13.2", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.mary_core = core

    async def require_creator(request: Request) -> None:
        if not _authorized(request.headers.get("Authorization")):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        # Deliberately minimal and unauthenticated for hosting health checks.
        return core.health()

    @app.post("/v1/turn")
    async def turn(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            payload = await request.json()
            model = TurnRequest.from_dict(payload)
            response = await asyncio.to_thread(core.process_turn, model)
            return response.to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/state")
    async def state(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.state()

    @app.get("/v1/memory/status")
    async def memory_status(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.memory_status()

    @app.get("/v1/conversation")
    async def conversation(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.conversation_status()

    @app.get("/v1/growth")
    async def growth(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.growth_status()

    @app.get("/v1/nodes")
    async def nodes(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.node_status()

    @app.post("/v1/nodes/register")
    async def register_node(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = NodeRegistrationRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.register_node, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/nodes/heartbeat")
    async def heartbeat_node(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = NodeHeartbeatRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.heartbeat_node, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (KeyError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/nodes/disconnect")
    async def disconnect_node(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = NodeHeartbeatRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.disconnect_node, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/nodes/route")
    async def route_capability(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CapabilityRouteRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.route_capability, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/nodes/task/preview")
    async def preview_capability_task(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CapabilityTaskPreviewRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.preview_capability_task, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/dashboard")
    async def dashboard(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.dashboard_status()

    @app.get("/v1/workspace")
    async def workspace(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.workspace_status()

    @app.post("/v1/workspace/action")
    async def workspace_action(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            payload = await request.json()
            model = WorkspaceActionRequest.from_dict(payload)
            return await asyncio.to_thread(core.workspace_action, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (KeyError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/runtime/action")
    async def runtime_action(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            payload = await request.json()
            model = RuntimeActionRequest.from_dict(payload)
            return await asyncio.to_thread(core.runtime_action, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.websocket("/v1/realtime")
    async def realtime(websocket: WebSocket) -> None:
        await websocket.accept()
        authorized = _authorized(websocket.headers.get("Authorization"))
        if not authorized:
            try:
                hello = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
            except Exception:
                await websocket.close(code=4401, reason="Authentication required")
                return
            authorized = isinstance(hello, dict) and hello.get("type") == "auth" and _authorized(str(hello.get("token") or ""))
        if not authorized:
            await websocket.close(code=4401, reason="Unauthorized")
            return
        await websocket.send_json({"type": "ready", **core.health()})
        try:
            while True:
                message = await websocket.receive_json()
                kind = str(message.get("type") or "turn") if isinstance(message, dict) else ""
                if kind == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                if kind != "turn":
                    await websocket.send_json({"type": "error", "error": "Unsupported realtime message type."})
                    continue
                try:
                    payload = dict(message.get("payload") or message)
                    payload.pop("type", None)
                    response = await asyncio.to_thread(core.process_turn, TurnRequest.from_dict(payload))
                    await websocket.send_json({"type": "turn.completed", "payload": response.to_dict()})
                except Exception as exc:
                    await websocket.send_json({"type": "turn.failed", "error": f"{type(exc).__name__}: {exc}"})
        except WebSocketDisconnect:
            return

    return app


def run_server() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Mary Core server requires `pip install uvicorn`. ") from exc

    host = os.getenv("MARY_CORE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("PORT") or os.getenv("MARY_CORE_PORT") or "8080")
    if not _token():
        insecure_local = os.getenv("MARY_CORE_ALLOW_INSECURE_LOCAL", "").strip().lower() in {"1", "true", "yes", "on"}
        if host not in {"127.0.0.1", "localhost", "::1"} or not insecure_local:
            raise RuntimeError("MARY_CORE_TOKEN is required. For explicit loopback-only development, set MARY_CORE_ALLOW_INSECURE_LOCAL=1.")
    uvicorn.run(create_app(), host=host, port=port, log_level=os.getenv("MARY_CORE_LOG_LEVEL", "info"))


if __name__ == "__main__":
    run_server()
