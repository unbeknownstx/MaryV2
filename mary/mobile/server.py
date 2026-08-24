"""Dependency-light HTTP/PWA bridge for the canonical MaryV2 runtime.

This module intentionally uses Python's standard-library HTTP server so the
mobile surface adds no mandatory Python package to MaryV2.  The browser app can use Mary's existing Vite desktop UI when a built desktop/dist
is present, and otherwise falls back to the bundled zero-build mobile_web shell.

Security model
--------------
* Loopback-only development can run without a token.
* Non-loopback hosts (including Replit) automatically require a bearer token.
  If MARY_MOBILE_TOKEN is absent, a strong token is generated and persisted
  under data/mobile/access_token.txt, then printed once at startup.
* API bodies are bounded and static paths are traversal-safe.
* The browser never receives provider API keys or environment secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
from threading import RLock
from time import monotonic
from typing import Any, Callable
from urllib.parse import urlparse

from mary.conversation import ConversationLane, classify_conversation_lane
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.turn_trace import build_turn_trace
from mary.desktop.projects import CreativeWorkspaceManager
from mary.ecosystem import MaryEcosystem
from mary.presence import PresenceEventType
from mary.runtime.application import MaryApplication, create_application
from mary.mobile.audio import MobileSpeechService


MOBILE_PROTOCOL_VERSION = "2"
MAX_REQUEST_BYTES = 256_000
MAX_AUDIO_REQUEST_BYTES = 12_000_000


def _json_safe(value: Any) -> Any:
    """Round-trip through JSON so HTTP responses cannot leak unserializable objects."""

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _is_loopback(host: str) -> bool:
    return str(host or "").strip().lower() in {"127.0.0.1", "localhost", "::1"}


def _default_host() -> str:
    configured = os.getenv("MARY_MOBILE_HOST", "").strip()
    if configured:
        return configured
    if os.getenv("REPL_ID") or os.getenv("REPL_SLUG") or os.getenv("REPLIT_DB_URL"):
        return "0.0.0.0"
    return "127.0.0.1"


def _default_port() -> int:
    raw = os.getenv("MARY_MOBILE_PORT") or os.getenv("PORT") or "8080"
    try:
        return max(1024, min(65535, int(raw)))
    except (TypeError, ValueError):
        return 8080


@dataclass(frozen=True)
class MobileAuth:
    token: str
    source: str
    token_path: Path | None

    @property
    def enabled(self) -> bool:
        return bool(self.token)


def _resolve_auth(*, host: str, data_root: Path) -> MobileAuth:
    configured = os.getenv("MARY_MOBILE_TOKEN", "").strip()
    if configured:
        return MobileAuth(configured, "environment", None)

    if _is_loopback(host):
        return MobileAuth("", "loopback", None)

    token_path = data_root / "mobile" / "access_token.txt"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = token_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""
    except OSError:
        existing = ""

    if existing:
        return MobileAuth(existing, "persisted", token_path)

    token = secrets.token_urlsafe(24)
    token_path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    return MobileAuth(token, "generated", token_path)


class MaryMobileRuntime:
    """Thread-safe transport facade over one canonical MaryApplication."""

    def __init__(self, application: MaryApplication | None = None) -> None:
        self.application = application or create_application(name="mary_mobile")
        self.ecosystem = MaryEcosystem(self.application.mary)
        self.creative_workspace = CreativeWorkspaceManager()
        self.speech = MobileSpeechService()
        self._lock = RLock()
        self._busy = False
        self._last_trace: dict[str, Any] = {}
        try:
            self.application.mary.avatar.ready()
        except Exception:
            pass

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def status(self) -> dict[str, Any]:
        with self._lock:
            mary_status = dict(self.application.mary.status() or {})
            cognition = dict(mary_status.get("cognition", {}) or {})
            environment = dict(self.application.mary.runtime_environment.snapshot() or {})
            return _json_safe(
                {
                    "name": mary_status.get("name", "Mary"),
                    "provider": cognition.get("llm", "runtime"),
                    "model": cognition.get("model", "MaryV2"),
                    "busy": self._busy,
                    "conversation": {"state": "thinking" if self._busy else "idle"},
                    "voice": {
                        **dict(self.speech.status().get("tts", {}) or {}),
                        "mode": "server_preferred_with_device_fallback",
                    },
                    "speech_to_text": {
                        **dict(self.speech.status().get("stt", {}) or {}),
                        "mode": "server_upload_with_browser_fallback",
                    },
                    "mobile": {
                        "protocol": MOBILE_PROTOCOL_VERSION,
                        "host_type": environment.get("host_type", "unknown"),
                        "effective_conversation_route": environment.get("effective_conversation_route", []),
                    },
                }
            )

    def avatar_state(self) -> dict[str, Any]:
        with self._lock:
            try:
                return _json_safe(self.application.mary.avatar.state.to_dict())
            except Exception:
                return {}

    def character_state(self, *, runtime_status: str | None = None) -> dict[str, Any]:
        with self._lock:
            resolved_status = runtime_status or ("thinking" if self._busy else "idle")
            return _json_safe(
                self.application.mary.live_state(runtime_status=resolved_status)
            )

    def dashboard_state(self, *, runtime_status: str | None = None) -> dict[str, Any]:
        with self._lock:
            resolved_status = runtime_status or ("thinking" if self._busy else "idle")
            payload = build_desktop_dashboard_state(
                self.application.mary,
                runtime_status=resolved_status,
            )
            payload["ecosystem"] = self.ecosystem.snapshot()
            try:
                payload["mind"] = self.application.mary.mind.status()
            except Exception as exc:
                payload["mind"] = {
                    "enabled": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            payload["mobile"] = {
                "protocol": MOBILE_PROTOCOL_VERSION,
                "surface": "pwa",
            }
            return _json_safe(payload)

    def ecosystem_state(self) -> dict[str, Any]:
        with self._lock:
            return _json_safe(self.ecosystem.snapshot())

    def mind_status(self) -> dict[str, Any]:
        with self._lock:
            try:
                return _json_safe(self.application.mary.mind.status())
            except Exception as exc:
                return {"enabled": False, "error": f"{type(exc).__name__}: {exc}"}

    def last_turn_trace(self) -> dict[str, Any]:
        with self._lock:
            return _json_safe(self._last_trace or self.ecosystem.metrics.last_turn() or {})

    def chat(self, text: str) -> dict[str, Any]:
        value = str(text or "").strip()
        if not value:
            raise ValueError("Message text cannot be empty.")
        if len(value) > 32_000:
            raise ValueError("Message is too long for the mobile transport.")

        with self._lock:
            if self._busy:
                raise RuntimeError("Mary is already processing a message.")
            self._busy = True

        started = monotonic()
        try:
            lane = classify_conversation_lane(value)
            pipeline_started = monotonic()
            result = self.application.run(
                value,
                metadata={"surface": "mobile", "transport": "http"},
            )
            pipeline_ms = (monotonic() - pipeline_started) * 1000.0
            if not result.success:
                raise RuntimeError(result.error or "Mary's pipeline did not complete.")

            response_text = str(result.output or "")
            mary = self.application.mary
            avatar_started = monotonic()
            delivery_plan: dict[str, Any] = {}
            try:
                values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
                cycle = values.get("cognitive_cycle")
                cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
                delivery_plan = dict(cycle_metadata.get("delivery_plan", {}) or {})
                mary.avatar.sync_emotion()
                avatar = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={"surface": "mobile", "delivery_plan": delivery_plan},
                ).to_dict()
            except Exception:
                try:
                    avatar = mary.avatar.state.to_dict()
                except Exception:
                    avatar = {}
            avatar_ms = (monotonic() - avatar_started) * 1000.0
            worker_total_ms = (monotonic() - started) * 1000.0
            voice_status = dict(self.speech.status().get("tts", {}) or {})
            trace = build_turn_trace(
                result,
                pipeline_ms=pipeline_ms,
                avatar_ms=avatar_ms,
                voice_payload={
                    "enabled": bool(voice_status.get("enabled", True)),
                    "provider": voice_status.get("provider") or "device_fallback",
                    "status": "deferred_mobile_playback",
                },
                worker_total_ms=worker_total_ms,
            )
            trace.setdefault("mobile", {})["lane"] = getattr(lane.lane, "value", str(lane.lane))
            self.ecosystem.record_turn(elapsed=result.elapsed, trace=trace)

            with self._lock:
                self._last_trace = trace

            return _json_safe(
                {
                    "text": response_text,
                    "canonical_text": response_text,
                    "avatar": avatar,
                    "voice": {
                        **voice_status,
                        "enabled": True,
                        "status": "ready",
                        "spoken_text": response_text,
                        "delivery_plan": delivery_plan,
                        "device_fallback": True,
                    },
                    "runtime": {
                        "turn_id": result.turn_id,
                        "elapsed": result.elapsed,
                        "success": True,
                        "trace": trace,
                        "conversation_lane": getattr(lane.lane, "value", str(lane.lane)),
                    },
                    "character": self.character_state(runtime_status="idle"),
                    "dashboard": self.dashboard_state(runtime_status="idle"),
                }
            )
        finally:
            with self._lock:
                self._busy = False


    def voice_status(self) -> dict[str, Any]:
        with self._lock:
            return _json_safe(self.speech.status())

    def synthesize_speech(
        self,
        text: str,
        *,
        user_text: str | None = None,
        delivery_plan: dict[str, Any] | None = None,
    ):
        return self.speech.synthesize(
            text,
            user_text=user_text,
            delivery_plan=delivery_plan,
        )

    def transcribe_audio(
        self,
        audio: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        return self.speech.transcribe(
            audio,
            filename=filename,
            content_type=content_type,
        )

    def _publish(self, event_type: PresenceEventType, summary: str, **metadata: Any) -> None:
        try:
            self.ecosystem.publish_workspace_event(
                event_type,
                summary,
                importance=float(metadata.pop("importance", 0.55)),
                metadata=metadata or None,
            )
        except Exception:
            pass

    def bridge_call(self, method: str, args: list[Any] | None = None) -> Any:
        """Implement the display-safe subset used by the shared desktop UI."""

        name = str(method or "").strip()
        values = list(args or [])
        with self._lock:
            if name == "getStatus":
                return self.status()
            if name == "getAvatarState":
                return self.avatar_state()
            if name == "getCharacterState":
                return self.character_state()
            if name == "getDashboardState":
                return self.dashboard_state()
            if name == "getEcosystemState":
                return self.ecosystem_state()
            if name == "getMindStatus":
                return self.mind_status()
            if name == "getLastTurnTrace":
                return self.last_turn_trace()
            if name == "getMobileVoiceStatus":
                return self.voice_status()
            if name == "rebuildCognitiveReservoir":
                try:
                    count = int(self.application.mary.mind.rebuild_reservoir())
                    return {"ok": True, "records": count, "status": self.mind_status()}
                except Exception as exc:
                    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if name == "addCommandItem":
                title = str(values[0] if values else "")
                kind = str(values[1] if len(values) > 1 else "task")
                item = self.ecosystem.command.add(title, kind=kind or "task")
                self._publish(PresenceEventType.COMMAND_CHANGED, f"Command Center added {item.get('title', '')}", item_id=item.get("id"))
                return {"ok": True, "item": item}
            if name == "updateCommandStatus":
                item = self.ecosystem.command.update(str(values[0]), status=str(values[1]))
                self._publish(PresenceEventType.COMMAND_CHANGED, f"Command Center updated {item.get('title', '')}", item_id=item.get("id"), status=item.get("status"))
                return {"ok": True, "item": item}
            if name == "startFocus":
                minutes = int(values[0])
                task = str(values[1] if len(values) > 1 else "")
                state = self.ecosystem.focus.start(minutes, task=task)
                self._publish(PresenceEventType.FOCUS_CHANGED, f"Focus started for {minutes} minutes", active=True, minutes=minutes)
                return {"ok": True, "focus": state}
            if name == "stopFocus":
                state = self.ecosystem.focus.stop()
                self._publish(PresenceEventType.FOCUS_CHANGED, "Focus session stopped", active=False)
                return {"ok": True, "focus": state}
            if name == "createStudyProject":
                project = self.ecosystem.study.create_project(str(values[0]), objective=str(values[1] if len(values) > 1 else ""))
                self._publish(PresenceEventType.STUDY_CHANGED, f"Study project created: {project.get('title', '')}", project_id=project.get("id"))
                return {"ok": True, "project": project}
            if name == "addStudyCard":
                card = self.ecosystem.study.add_card(str(values[0]), str(values[1]), str(values[2]))
                return {"ok": True, "card": card}
            if name == "reviewStudyCard":
                card = self.ecosystem.study.review(str(values[0]), str(values[1]), int(values[2]))
                return {"ok": True, "card": card}
            if name == "personalSearch":
                return {"ok": True, "results": self.ecosystem.search.search(str(values[0]))}
            if name == "markNoticeRead":
                return bool(self.ecosystem.inbox.mark_read(str(values[0]), True))
            if name == "createResearchThread":
                thread = self.ecosystem.research.create(str(values[0]), question=str(values[1] if len(values) > 1 else ""))
                return {"ok": True, "thread": thread}
            if name == "playArcade":
                return {"ok": True, **self.ecosystem.arcade.play(str(values[0]), str(values[1] if len(values) > 1 else ""))}
            if name == "getIdleAction":
                focus_active = bool(self.ecosystem.focus.snapshot().get("active"))
                return self.ecosystem.presence.idle_tick(focus_active=focus_active)
            if name == "getYouTubeStatus":
                return self.ecosystem.youtube.status()
            if name == "searchYouTube":
                try:
                    results = self.ecosystem.youtube.search(str(values[0]))
                    return {"ok": True, "results": results, "status": self.ecosystem.youtube.status()}
                except Exception as exc:
                    return {"ok": False, "error": str(exc), "results": [], "status": self.ecosystem.youtube.status()}
            if name == "saveYouTubeToResearch":
                thread = self.ecosystem.research.create(str(values[0] or "YouTube research"), question=str(values[1] if len(values) > 1 else ""))
                return {"ok": True, "thread": thread}

            # Native-desktop-only surfaces remain explicit rather than pretending
            # the phone can launch local Windows applications or file pickers.
            if name in {"getIntegrationState"}:
                return {"creative_apps": [], "mobile_limited": True}
            if name == "getCreativeWorkspaceState":
                try:
                    return self.creative_workspace.status()
                except Exception as exc:
                    return {"configured": False, "error": f"{type(exc).__name__}: {exc}", "files": []}
            if name == "readCreativeTextFile":
                try:
                    return {"ok": True, **self.creative_workspace.read_text(str(values[0] if values else ""))}
                except Exception as exc:
                    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if name == "saveCreativeTextFile":
                try:
                    relative_path = str(values[0] if values else "")
                    content = str(values[1] if len(values) > 1 else "")
                    result = self.creative_workspace.save_text(relative_path, content)
                    self._publish(
                        PresenceEventType.CREATIVE_CHANGED,
                        f"Creative text saved from mobile: {relative_path}",
                        relative_path=relative_path[:240],
                    )
                    return {"ok": True, **result}
                except Exception as exc:
                    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if name in {"chooseSearchRoot", "chooseMediaFile", "chooseCreativeFile", "chooseCreativeWorkspace"}:
                return {"selected": False, "mobile_limited": True, "reason": "Configure the workspace on Mary host or with MARY_CREATIVE_WORKSPACE."}
            if name in {"openCreativeWorkspaceFolder", "openDataFolder", "openWorkspaceFolder", "launchCreativeApp"}:
                return False

        raise KeyError(f"Unsupported mobile bridge method: {name}")

    def close(self) -> None:
        with self._lock:
            self.application.close()


class MaryMobileRequestHandler(SimpleHTTPRequestHandler):
    server_version = "MaryMobile/1"

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    @property
    def mary_server(self) -> "MaryMobileServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[MaryMobile] {self.address_string()} - {fmt % args}", flush=True)

    def _allowed_origin(self) -> str:
        origin = str(self.headers.get("Origin", "") or "").strip()
        if not origin:
            return ""
        defaults = {"capacitor://localhost", "http://localhost", "https://localhost", "null"}
        configured = {
            item.strip().rstrip("/")
            for item in os.getenv("MARY_MOBILE_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        }
        if origin.rstrip("/") in defaults | configured:
            return origin
        return ""

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not urlparse(self.path).path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        origin = self._allowed_origin()
        if self.headers.get("Origin") and not origin:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Mary-Audio-Filename")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def end_headers(self) -> None:
        origin = self._allowed_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header(
                "Access-Control-Expose-Headers",
                "X-Mary-Voice-Provider, X-Mary-Voice-Model, X-Mary-Voice-Status, X-Mary-Voice-Cache",
            )
        if not urlparse(self.path).path.startswith("/api/"):
            suffix = Path(urlparse(self.path).path).suffix.lower()
            if suffix in {".html", ".js", ".css", ".webmanifest"} or self.path == "/":
                self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        super().end_headers()

    def _authorized(self) -> bool:
        expected = self.mary_server.auth.token
        if not expected:
            return True
        supplied = self.headers.get("Authorization", "")
        return secrets.compare_digest(supplied, f"Bearer {expected}")

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(_json_safe(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_audio(self, audio: bytes, *, mime_type: str, metadata: dict[str, Any]) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", str(mime_type or "application/octet-stream"))
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Mary-Voice-Status", str(metadata.get("status") or "success"))
        self.send_header("X-Mary-Voice-Provider", str(metadata.get("provider") or "unknown")[:120])
        self.send_header("X-Mary-Voice-Model", str(metadata.get("model") or "")[:160])
        self.send_header("X-Mary-Voice-Cache", "hit" if metadata.get("cached") else "miss")
        self.end_headers()
        self.wfile.write(audio)

    def _read_bytes(self, *, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc
        if length <= 0:
            raise ValueError("Request body is empty.")
        if length > maximum:
            raise OverflowError("Request body is too large.")
        return self.rfile.read(length)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc
        if length <= 0:
            return {}
        if length > MAX_REQUEST_BYTES:
            raise OverflowError("Request body is too large.")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(value, dict):
            raise ValueError("Request JSON must be an object.")
        return value

    def _require_api_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json({"ok": False, "error": "Unauthorized", "auth_required": True}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            if not self._require_api_auth():
                return
            self._send_json(
                {
                    "ok": True,
                    "service": "MaryV2 Mobile",
                    "protocol": MOBILE_PROTOCOL_VERSION,
                    "auth": "token" if self.mary_server.auth.enabled else "loopback",
                    "status": self.mary_server.runtime.status(),
                }
            )
            return
        if path == "/api/state":
            if not self._require_api_auth():
                return
            self._send_json(self.mary_server.runtime.dashboard_state())
            return
        if path == "/api/trace":
            if not self._require_api_auth():
                return
            self._send_json(self.mary_server.runtime.last_turn_trace())
            return
        if path == "/api/voice/status":
            if not self._require_api_auth():
                return
            self._send_json({"ok": True, **self.mary_server.runtime.voice_status()})
            return
        if path.startswith("/api/"):
            self._send_json({"ok": False, "error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
            return

        # SPA fallback: unknown extensionless routes reopen the Mary UI.
        parsed = Path(path)
        if path != "/" and not parsed.suffix:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._send_json({"ok": False, "error": "POST is only supported for API routes."}, HTTPStatus.NOT_FOUND)
            return
        if not self._require_api_auth():
            return
        try:
            if path == "/api/stt":
                raw = self._read_bytes(maximum=MAX_AUDIO_REQUEST_BYTES)
                payload = self.mary_server.runtime.transcribe_audio(
                    raw,
                    filename=self.headers.get("X-Mary-Audio-Filename"),
                    content_type=self.headers.get("Content-Type"),
                )
                self._send_json({"ok": True, **payload})
                return

            body = self._read_json()
            if path == "/api/chat":
                payload = self.mary_server.runtime.chat(str(body.get("text") or ""))
                self._send_json({"ok": True, **payload})
                return
            if path == "/api/tts":
                delivery_plan = body.get("delivery_plan") or {}
                if not isinstance(delivery_plan, dict):
                    raise ValueError("delivery_plan must be a JSON object.")
                speech = self.mary_server.runtime.synthesize_speech(
                    str(body.get("text") or ""),
                    user_text=str(body.get("user_text") or "") or None,
                    delivery_plan=delivery_plan,
                )
                if speech.successful:
                    self._send_audio(
                        speech.audio,
                        mime_type=speech.mime_type,
                        metadata={**speech.metadata, "cached": speech.cached},
                    )
                else:
                    self._send_json(
                        {"ok": False, "fallback": "device", **speech.metadata},
                        HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                return
            if path == "/api/bridge":
                method = str(body.get("method") or "")
                args = body.get("args") or []
                if not isinstance(args, list):
                    raise ValueError("Bridge args must be a JSON array.")
                payload = self.mary_server.runtime.bridge_call(method, args)
                self._send_json({"ok": True, "result": payload})
                return
            self._send_json({"ok": False, "error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
        except OverflowError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except KeyError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.CONFLICT)
        except Exception as exc:
            self._send_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


class MaryMobileServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        runtime: MaryMobileRuntime,
        static_root: Path,
        auth: MobileAuth,
    ) -> None:
        self.runtime = runtime
        self.static_root = Path(static_root).resolve()
        self.auth = auth
        handler = partial(MaryMobileRequestHandler, directory=str(self.static_root))
        super().__init__(address, handler)

    def server_close(self) -> None:
        try:
            self.runtime.close()
        finally:
            super().server_close()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _static_root(root: Path) -> Path:
    configured = os.getenv("MARY_MOBILE_STATIC_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    # Mobile is a first-class surface, not a responsive fallback for Desktop.
    # Prefer the dedicated phone UI even when desktop/dist happens to exist on
    # the same development host (common on Replit/GitHub/PC working copies).
    standalone = root / "mobile_web"
    if (standalone / "index.html").exists():
        return standalone

    # An explicit escape hatch remains for development/recovery builds where
    # only the compiled desktop frontend is available.
    built = root / "desktop" / "dist"
    if (built / "index.html").exists():
        return built
    return root / "desktop"


def run_mobile_server(
    *,
    host: str | None = None,
    port: int | None = None,
    application: MaryApplication | None = None,
) -> None:
    root = _project_root()
    resolved_host = host or _default_host()
    resolved_port = int(port or _default_port())
    runtime = MaryMobileRuntime(application)
    static_root = _static_root(root)
    auth = _resolve_auth(host=resolved_host, data_root=Path(runtime.application.mary.config.paths.data))

    if not (static_root / "index.html").exists():
        runtime.close()
        raise RuntimeError(
            f"Mobile UI not found at {static_root}. Run `cd desktop && npm ci && npm run build` first."
        )

    server = MaryMobileServer(
        (resolved_host, resolved_port),
        runtime=runtime,
        static_root=static_root,
        auth=auth,
    )

    print("=" * 68, flush=True)
    print("MARYV2 MOBILE COMPANION", flush=True)
    print("=" * 68, flush=True)
    print(f"Host: {resolved_host}", flush=True)
    print(f"Port: {resolved_port}", flush=True)
    print(f"UI:   {static_root}", flush=True)
    if auth.enabled:
        print("Mobile API protection: bearer token", flush=True)
        if auth.source == "generated":
            print("", flush=True)
            print("FIRST-RUN MOBILE ACCESS TOKEN", flush=True)
            print(auth.token, flush=True)
            print("Enter this once in the Mary mobile app. It is saved on this device.", flush=True)
        elif auth.source == "persisted":
            print(f"Token loaded from: {auth.token_path}", flush=True)
        else:
            print("Token loaded from MARY_MOBILE_TOKEN.", flush=True)
    else:
        print("Mobile API protection: loopback-only (no token required)", flush=True)
    print("", flush=True)
    print("The mobile surface is a client of the canonical MaryApplication.", flush=True)
    print("It does not create a second Mary identity or memory store.", flush=True)
    print("=" * 68, flush=True)

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run_mobile_server()
