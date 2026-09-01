"""ASGI/HTTP/WebSocket transport for the MaryV2 13.2 unified core."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
import secrets
from time import monotonic
from typing import Any
import zipfile
import json

try:
    from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
except ImportError:  # pragma: no cover - handled by create_app/run_server
    FastAPI = HTTPException = Request = Response = WebSocket = WebSocketDisconnect = None

from mary.core.service import MaryCoreService
from mary.protocol.models import (
    CapabilityRouteRequest,
    CapabilityTaskDispatchRequest,
    CapabilityTaskPreviewRequest,
    CreatorOfflineRequest,
    CreatorSurfaceRequest,
    NodeHeartbeatRequest,
    NodeRegistrationRequest,
    NodeTaskCompletionRequest,
    NodeTaskPollRequest,
    RuntimeActionRequest,
    TurnRequest,
    WorkspaceActionRequest,
)
from mary.runtime.turn_observability import (
    TurnTraceRecorder,
    bind_turn_trace,
    bounded_identifier,
    classify_failure,
    reset_turn_trace,
    upstream_request_hash,
)

MAX_WORKSPACE_ACTION_BYTES = 16_384


def _token() -> str:
    return os.getenv("MARY_CORE_TOKEN", "").strip()


def _authorized(value: str | None) -> bool:
    expected = _token()
    if not expected:
        return os.getenv(
            "MARY_CORE_ALLOW_INSECURE_LOCAL",
            "",
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    supplied = str(value or "")

    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()

    return bool(supplied) and secrets.compare_digest(
        supplied,
        expected,
    )


def _secure_node_transport(request: Request) -> bool:
    """Accept node credentials only over HTTPS (plus in-process tests)."""

    # ASGI server/proxy middleware must resolve trusted forwarded headers into
    # request.url.scheme. Never trust a caller-supplied header directly here.
    scheme = str(request.url.scheme or "").lower()
    client_host = str(
        getattr(request.client, "host", "")
        or ""
    ).lower()
    return scheme == "https" or client_host == "testclient"


def create_app(service: MaryCoreService | None = None):
    if FastAPI is None:  # pragma: no cover - installation guidance
        raise RuntimeError(
            "Mary Core HTTP transport requires `pip install fastapi uvicorn`."
        )

    core = service or MaryCoreService()

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            await asyncio.to_thread(core.close)

    app = FastAPI(
        title="MaryV2 Core",
        version="13.2",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.state.mary_core = core

    async def bounded_json(
        request: Request,
        *,
        limit: int,
    ) -> Any:
        raw_length = str(
            request.headers.get(
                "Content-Length",
                "",
            )
            or ""
        ).strip()
        if raw_length:
            try:
                if int(raw_length) > limit:
                    raise HTTPException(
                        status_code=413,
                        detail="Request body too large.",
                    )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Content-Length.",
                ) from exc

        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(
                    status_code=413,
                    detail="Request body too large.",
                )
            chunks.append(chunk)
        try:
            return json.loads(
                b"".join(chunks)
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail="Request body must be valid JSON.",
            ) from exc

    async def require_creator(request: Request) -> None:
        if not _authorized(
            request.headers.get("Authorization")
        ):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
            )

    async def require_node(request: Request, node_id: str) -> str:
        """Authenticate device-channel calls independently of creator access."""
        token = str(request.headers.get("X-Mary-Node-Token") or "")
        if not core.validate_node_token(node_id, token):
            raise HTTPException(status_code=401, detail="Valid scoped node token required")
        return token

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        # Deliberately minimal and unauthenticated for hosting health checks.
        return core.health()

    @app.post("/v1/turn")
    async def turn(request: Request, response: Response) -> dict[str, Any]:
        supplied_request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Railway-Request-ID")
            or request.headers.get("X-Correlation-ID")
        )
        trace = TurnTraceRecorder(
            request_id=bounded_identifier(None),
            core_instance_id=core.instance_id,
            core_uptime_ms=lambda: (monotonic() - core.started_monotonic) * 1000.0,
            sink=core.record_turn_trace,
            upstream_request_hash=upstream_request_hash(supplied_request_id),
        )
        token = bind_turn_trace(trace)
        response.headers["X-Mary-Request-ID"] = trace.request_id
        try:
            with trace.stage(
                "authentication",
                failure_kind="authentication_failure",
            ):
                await require_creator(request)
            with trace.stage("core_ingress", failure_kind="invalid_request"):
                payload = await request.json()
                model = TurnRequest.from_dict(payload)
                trace.set_turn_id(model.turn_id)
                trace.set_conversation_id(model.conversation_id)

            turn_response = await asyncio.to_thread(
                core.process_turn,
                model,
            )

            with trace.stage(
                "response_serialization",
                failure_kind="serialization_failure",
            ):
                serialized = turn_response.to_dict()
            trace.finish(outcome="replayed" if trace.replayed else "success")
            return serialized

        except asyncio.CancelledError as exc:
            # ASGI cancellation is the strongest application-level evidence
            # that the upstream requester disconnected. The worker thread may
            # finish independently, but this request trace terminates here.
            trace.finish(
                outcome="failure",
                failure_kind="upstream_disconnect",
                error=exc,
            )
            raise

        except HTTPException as exc:
            failure_kind = (
                "authentication_failure"
                if int(exc.status_code) in {401, 403}
                else "invalid_request"
            )
            trace.finish(
                outcome="failure",
                failure_kind=failure_kind,
                error=exc,
            )
            headers = dict(exc.headers or {})
            headers["X-Mary-Request-ID"] = trace.request_id
            exc.headers = headers
            raise

        except ValueError as exc:
            trace.finish(
                outcome="failure",
                failure_kind="invalid_request",
                error=exc,
            )
            raise HTTPException(
                status_code=422,
                detail="Invalid Mary Core turn request.",
                headers={"X-Mary-Request-ID": trace.request_id},
            ) from exc

        except RuntimeError as exc:
            failure_kind = trace.latest_failure_kind(
                classify_failure(
                    exc,
                    default="application_exception",
                )
            )
            trace.finish(
                outcome="failure",
                failure_kind=failure_kind,
                error=exc,
            )
            raise HTTPException(
                status_code=500 if failure_kind == "serialization_failure" else 409,
                detail=(
                    "Mary Core response serialization failed."
                    if failure_kind == "serialization_failure"
                    else "Mary Core turn failed."
                ),
                headers={"X-Mary-Request-ID": trace.request_id},
            ) from exc
        except Exception as exc:
            trace.finish(
                outcome="failure",
                failure_kind=classify_failure(
                    exc,
                    default="application_exception",
                ),
                error=exc,
            )
            raise HTTPException(
                status_code=500,
                detail="Mary Core turn failed.",
                headers={"X-Mary-Request-ID": trace.request_id},
            ) from exc
        finally:
            reset_turn_trace(token)

    @app.get("/v1/state")
    async def state(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.state()

    @app.get("/v1/admin/turn-traces")
    @app.get("/v1/turn-traces")
    async def turn_traces(request: Request) -> dict[str, Any]:
        await require_creator(request)
        request_id = request.query_params.get("request_id")
        turn_id = request.query_params.get("turn_id")
        raw_limit = request.query_params.get("limit", "20")
        try:
            limit = int(raw_limit)
            traces = core.query_turn_traces(
                request_id=request_id,
                turn_id=turn_id,
                limit=limit,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid turn trace query.",
            ) from exc
        return {
            "traces": traces,
            "count": len(traces),
            "limit": max(1, min(40, limit)),
        }

    @app.post("/v1/admin/backups")
    async def create_durable_backup(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            return await asyncio.to_thread(core.create_durable_backup)
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(
                status_code=409,
                detail="Durable-state backup failed safely.",
            ) from exc

    @app.get("/v1/admin/durable-state")
    async def durable_state(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            return await asyncio.to_thread(core.durable_state_status)
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=409,
                detail="Durable-state fingerprint failed safely.",
            ) from exc

    @app.get("/v1/creator-surfaces/status")
    async def creator_surface_status(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.creator_lifecycle_status()

    @app.post("/v1/creator-surfaces/register")
    async def register_creator_surface(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorSurfaceRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.register_creator_surface, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/creator-surfaces/renew")
    async def renew_creator_surface(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorSurfaceRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.renew_creator_surface, model)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/creator-surfaces/visibility")
    async def update_creator_visibility(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorSurfaceRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.update_creator_visibility, model)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/creator-surfaces/disconnect")
    async def disconnect_creator_surface(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorSurfaceRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.disconnect_creator_surface, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/creator-surfaces/wake")
    async def wake_creator_surfaces(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorSurfaceRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.wake_creator_surfaces, model)
        except (ValueError, KeyError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/creator-surfaces/offline")
    async def set_creator_offline(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            model = CreatorOfflineRequest.from_dict(await request.json())
            return await asyncio.to_thread(core.set_creator_offline, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        try:
            if not _secure_node_transport(request):
                raise HTTPException(
                    status_code=426,
                    detail="Node registration requires HTTPS.",
                )
            creator_authorized = _authorized(request.headers.get("Authorization"))
            enrollment_grant = request.headers.get("X-Mary-Enrollment-Grant")
            node_token = request.headers.get("X-Mary-Node-Token")
            device_credential = request.headers.get("X-Mary-Device-Credential")
            if not creator_authorized and not enrollment_grant and not node_token and not device_credential:
                raise HTTPException(
                    status_code=401,
                    detail="Node token, scoped enrollment grant, or device credential required",
                )
            model = NodeRegistrationRequest.from_dict(
                await request.json()
            )

            return await asyncio.to_thread(
                core.register_node,
                model,
                node_token=node_token,
                enrollment_grant=enrollment_grant,
                device_credential=device_credential,
                creator_authorized=creator_authorized,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except PermissionError as exc:
            raise HTTPException(
                status_code=401,
                detail=str(exc),
            ) from exc

        except RuntimeError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/enrollment-grants")
    async def issue_node_enrollment_grant(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            payload = await request.json()
            return await asyncio.to_thread(
                core.issue_enrollment_grant,
                str(payload.get("node_id") or ""),
                expires_in_seconds=float(payload.get("expires_in_seconds", 900)),
                max_uses=int(payload.get("max_uses", 10)),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/nodes/enrollment-grants")
    async def node_enrollment_grants(request: Request) -> dict[str, Any]:
        await require_creator(request)
        return core.enrollment_grant_status()

    @app.post("/v1/nodes/revoke")
    async def revoke_node(request: Request) -> dict[str, Any]:
        await require_creator(request)
        try:
            payload = await request.json()
            return await asyncio.to_thread(
                core.revoke_node, str(payload.get("node_id") or ""),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/nodes/heartbeat")
    async def heartbeat_node(request: Request) -> dict[str, Any]:
        try:
            model = NodeHeartbeatRequest.from_dict(
                await request.json()
            )
            node_token = await require_node(request, model.node_id)

            return await asyncio.to_thread(
                core.heartbeat_node,
                model,
                node_token=node_token,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            KeyError,
            RuntimeError, PermissionError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/disconnect")
    async def disconnect_node(request: Request) -> dict[str, Any]:
        try:
            model = NodeHeartbeatRequest.from_dict(
                await request.json()
            )
            node_token = await require_node(request, model.node_id)

            return await asyncio.to_thread(
                core.disconnect_node,
                model,
                node_token=node_token,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (RuntimeError, PermissionError) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/route")
    async def route_capability(request: Request) -> dict[str, Any]:
        await require_creator(request)

        try:
            model = CapabilityRouteRequest.from_dict(
                await request.json()
            )

            return await asyncio.to_thread(
                core.route_capability,
                model,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/task/preview")
    async def preview_capability_task(request: Request) -> dict[str, Any]:
        await require_creator(request)

        try:
            model = CapabilityTaskPreviewRequest.from_dict(
                await request.json()
            )

            return await asyncio.to_thread(
                core.preview_capability_task,
                model,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/task/dispatch")
    async def dispatch_capability_task(request: Request) -> dict[str, Any]:
        await require_creator(request)

        try:
            model = CapabilityTaskDispatchRequest.from_dict(
                await request.json()
            )

            return await asyncio.to_thread(
                core.dispatch_capability_task,
                model,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            LookupError,
            RuntimeError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/task/poll")
    async def poll_capability_task(request: Request) -> dict[str, Any]:
        try:
            model = NodeTaskPollRequest.from_dict(
                await request.json()
            )
            node_token = await require_node(request, model.node_id)

            return await asyncio.to_thread(
                core.poll_capability_task,
                model,
                node_token=node_token,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            KeyError,
            RuntimeError, PermissionError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/nodes/task/complete")
    async def complete_capability_task(request: Request) -> dict[str, Any]:
        try:
            model = NodeTaskCompletionRequest.from_dict(
                await request.json()
            )
            node_token = await require_node(request, model.node_id)

            return await asyncio.to_thread(
                core.complete_capability_task,
                model,
                node_token=node_token,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            KeyError,
            PermissionError,
            RuntimeError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.get("/v1/nodes/task/{task_id}")
    async def capability_task_status(
        task_id: str,
        request: Request,
    ) -> dict[str, Any]:
        await require_creator(request)

        try:
            return await asyncio.to_thread(
                core.capability_task_status,
                task_id,
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

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
            payload = await bounded_json(
                request,
                limit=MAX_WORKSPACE_ACTION_BYTES,
            )

            model = WorkspaceActionRequest.from_dict(
                payload
            )

            return await asyncio.to_thread(
                core.workspace_action,
                model,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            KeyError,
            RuntimeError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.post("/v1/runtime/action")
    async def runtime_action(request: Request) -> dict[str, Any]:
        await require_creator(request)

        try:
            payload = await request.json()

            model = RuntimeActionRequest.from_dict(
                payload
            )

            return await asyncio.to_thread(
                core.runtime_action,
                model,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except RuntimeError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

    @app.websocket("/v1/realtime")
    async def realtime(
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        authorized = _authorized(
            websocket.headers.get(
                "Authorization"
            )
        )

        if not authorized:
            try:
                hello = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=10.0,
                )

            except Exception:
                await websocket.close(
                    code=4401,
                    reason="Authentication required",
                )
                return

            authorized = (
                isinstance(
                    hello,
                    dict,
                )
                and hello.get("type") == "auth"
                and _authorized(
                    str(
                        hello.get(
                            "token"
                        )
                        or ""
                    )
                )
            )

        if not authorized:
            await websocket.close(
                code=4401,
                reason="Unauthorized",
            )
            return

        await websocket.send_json(
            {
                "type": "ready",
                **core.health(),
            }
        )

        try:
            while True:
                message = await websocket.receive_json()

                kind = (
                    str(
                        message.get("type")
                        or "turn"
                    )
                    if isinstance(
                        message,
                        dict,
                    )
                    else ""
                )

                if kind == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong"
                        }
                    )
                    continue

                if kind != "turn":
                    await websocket.send_json(
                        {
                            "type": "error",
                            "error": (
                                "Unsupported realtime message type."
                            ),
                        }
                    )
                    continue

                try:
                    payload = dict(
                        message.get(
                            "payload"
                        )
                        or message
                    )

                    payload.pop(
                        "type",
                        None,
                    )

                    response = await asyncio.to_thread(
                        core.process_turn,
                        TurnRequest.from_dict(
                            payload
                        ),
                    )

                    await websocket.send_json(
                        {
                            "type": "turn.completed",
                            "payload": (
                                response.to_dict()
                            ),
                        }
                    )

                except Exception as exc:
                    await websocket.send_json(
                        {
                            "type": "turn.failed",
                            "error": (
                                f"{type(exc).__name__}: {exc}"
                            ),
                        }
                    )

        except WebSocketDisconnect:
            return

    return app


def run_server() -> None:
    try:
        import uvicorn

    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Mary Core server requires `pip install uvicorn`. "
        ) from exc

    host = (
        os.getenv(
            "MARY_CORE_HOST",
            "127.0.0.1",
        ).strip()
        or "127.0.0.1"
    )

    port = int(
        os.getenv("PORT")
        or os.getenv(
            "MARY_CORE_PORT"
        )
        or "8080"
    )

    if not _token():
        insecure_local = (
            os.getenv(
                "MARY_CORE_ALLOW_INSECURE_LOCAL",
                "",
            )
            .strip()
            .lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        if (
            host
            not in {
                "127.0.0.1",
                "localhost",
                "::1",
            }
            or not insecure_local
        ):
            raise RuntimeError(
                "MARY_CORE_TOKEN is required. "
                "For explicit loopback-only development, "
                "set MARY_CORE_ALLOW_INSECURE_LOCAL=1."
            )

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level=os.getenv(
            "MARY_CORE_LOG_LEVEL",
            "info",
        ),
    )


if __name__ == "__main__":
    run_server()