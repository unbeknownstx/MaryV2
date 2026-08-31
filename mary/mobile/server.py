"""Dependency-light HTTP/PWA bridge for the canonical MaryV2 runtime.

This module intentionally uses Python's standard-library HTTP server so the
mobile surface adds no mandatory Python package to MaryV2. The browser app can
use Mary's existing Vite desktop UI when a built desktop/dist is present, and
otherwise falls back to the bundled zero-build mobile_web shell.

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
import re
import secrets
from threading import RLock
from time import monotonic, sleep
from typing import Any, Callable
from urllib.parse import urlparse

from mary.conversation import ConversationLane, classify_conversation_lane
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.turn_trace import build_turn_trace
from mary.desktop.projects import CreativeWorkspaceManager
from mary.presence import PresenceEventType
from mary.runtime.application import MaryApplication, create_application
from mary.mobile.audio import MobileSpeechService
from mary.mobile.voice_lab import VoiceLabStore, BASELINE as VOICE_BASELINE
from mary.protocol.client import MaryClient, MaryProtocolError
from mary.experience import build_experience_snapshot


MOBILE_PROTOCOL_VERSION = "4"
MAX_REQUEST_BYTES = 256_000
MAX_AUDIO_REQUEST_BYTES = 12_000_000
_SAFE_TRACE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")


def _clean_conversation_id(
    value: Any,
    fallback: str = "creator-primary",
) -> str:
    """Return a bounded transport-safe conversation/session identifier."""

    raw = (
        str(value or "").strip()
        or str(fallback or "creator-primary").strip()
    )

    cleaned = "".join(
        ch if (ch.isalnum() or ch in "._:-") else "-"
        for ch in raw
    ).strip("-._:")

    return (
        cleaned
        or "creator-primary"
    )[:160]


def _json_safe(
    value: Any,
) -> Any:
    """Round-trip through JSON so HTTP responses cannot leak unserializable objects."""

    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    )


def _character_sourcebook_inventory(
    value: Any,
) -> dict[str, int]:
    """Return the bounded count-only Sourcebook projection used by Mobile."""

    sourcebook = dict(
        value
        or {}
    )
    try:
        records = max(
            0,
            min(
                int(
                    sourcebook.get(
                        "records",
                        0,
                    )
                ),
                1_000_000,
            ),
        )
    except (TypeError, ValueError):
        records = 0
    return {
        "records": records,
    }


def _is_loopback(
    host: str,
) -> bool:
    return str(
        host or ""
    ).strip().lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _default_host() -> str:
    configured = os.getenv(
        "MARY_MOBILE_HOST",
        "",
    ).strip()

    if configured:
        return configured

    if (
        os.getenv("REPL_ID")
        or os.getenv("REPL_SLUG")
        or os.getenv("REPLIT_DB_URL")
    ):
        return "0.0.0.0"

    return "127.0.0.1"


def _default_port() -> int:
    raw = (
        os.getenv("MARY_MOBILE_PORT")
        or os.getenv("PORT")
        or "8080"
    )

    try:
        return max(
            1024,
            min(
                65535,
                int(raw),
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        return 8080


@dataclass(frozen=True)
class MobileAuth:
    token: str
    source: str
    token_path: Path | None

    @property
    def enabled(
        self,
    ) -> bool:
        return bool(
            self.token
        )


def _resolve_auth(
    *,
    host: str,
    data_root: Path,
) -> MobileAuth:
    configured = os.getenv(
        "MARY_MOBILE_TOKEN",
        "",
    ).strip()

    if configured:
        return MobileAuth(
            configured,
            "environment",
            None,
        )

    if _is_loopback(
        host
    ):
        return MobileAuth(
            "",
            "loopback",
            None,
        )

    token_path = (
        data_root
        / "mobile"
        / "access_token.txt"
    )

    token_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        existing = token_path.read_text(
            encoding="utf-8"
        ).strip()

    except FileNotFoundError:
        existing = ""

    except OSError:
        existing = ""

    if existing:
        return MobileAuth(
            existing,
            "persisted",
            token_path,
        )

    token = secrets.token_urlsafe(
        24
    )

    token_path.write_text(
        token + "\n",
        encoding="utf-8",
    )

    try:
        os.chmod(
            token_path,
            0o600,
        )

    except OSError:
        pass

    return MobileAuth(
        token,
        "generated",
        token_path,
    )


class MaryRemoteMobileRuntime:
    """Compatibility facade that makes the existing mobile UI a Mary Core client.

    When ``MARY_CORE_URL`` is configured this class deliberately does *not*
    construct ``Mary`` or ``MaryApplication``. Replit/mobile becomes a thin
    interface/proxy while identity and canonical state remain owned by the one
    remote Mary Core deployment.
    """

    def __init__(
        self,
        core_url: str,
        *,
        token: str,
        device_id: str = "replit-mobile",
    ) -> None:
        self.client = MaryClient(
            core_url,
            token=token,
            device_id=device_id,
        )

        # Keep constructor compatibility for lightweight test/fake clients while
        # still identifying the real protocol surface when supported.
        try:
            self.client.surface = "mobile"

        except Exception:
            pass

        self.speech = (
            MobileSpeechService()
        )

        self._lock = RLock()

        self._busy = False

        self._last_trace: dict[
            str,
            Any,
        ] = {}

        self._last_feedback_context: dict[
            str,
            Any,
        ] = {}

        self._conversation_id = (
            os.getenv(
                "MARY_CONVERSATION_ID",
                "creator-primary",
            ).strip()
            or "creator-primary"
        )

        # The mobile HTTP process represents one browser/native surface to
        # Core. Keep only the bounded identifier returned by Core; no presence
        # state is reconstructed or persisted by this proxy.
        self._surface_id: str | None = None

        configured = os.getenv(
            "MARY_MOBILE_PROXY_DATA_DIR",
            "",
        ).strip()

        self.data_root = (
            Path(
                configured
            )
            .expanduser()
            .resolve()
            if configured
            else (
                _project_root()
                / "data"
                / "mobile_proxy"
            )
        )

        self.data_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    @property
    def busy(
        self,
    ) -> bool:
        with self._lock:
            return self._busy

    def status(
        self,
    ) -> dict[str, Any]:
        state = (
            self.client
            .state()
        )

        conversation = (
            self.client
            .conversation_status()
        )

        mary_state = dict(
            state.get(
                "mary",
                {},
            )
            or {}
        )

        return _json_safe(
            {
                "name": mary_state.get(
                    "name",
                    "Mary",
                ),
                "provider": "mary-core",
                "model": "MaryV2",
                "busy": self.busy,
                "conversation": {
                    "state": (
                        "thinking"
                        if self.busy
                        else "idle"
                    )
                },
                "voice": {
                    **dict(
                        self.speech
                        .status()
                        .get(
                            "tts",
                            {},
                        )
                        or {}
                    ),
                    "mode": (
                        "server_preferred_with_device_fallback"
                    ),
                },
                "speech_to_text": {
                    **dict(
                        self.speech
                        .status()
                        .get(
                            "stt",
                            {},
                        )
                        or {}
                    ),
                    "mode": (
                        "server_upload_with_browser_fallback"
                    ),
                },
                "mobile": {
                    "protocol": MOBILE_PROTOCOL_VERSION,
                    "authority": "remote_mary_core",
                    "conversation_id": self._conversation_id,
                },
                "engagement": conversation.get(
                    "engagement",
                    {},
                ),
                "realtime": conversation.get(
                    "realtime",
                    {},
                ),
                "nodes": state.get(
                    "nodes",
                    {},
                ),
            }
        )

    @staticmethod
    def _clean_surface_id(
        value: Any,
    ) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        cleaned = "".join(
            char if (char.isalnum() or char in "._:-") else "-"
            for char in raw
        ).strip("-._:")
        return cleaned[:160] or None

    def surface_register(
        self,
        *,
        surface_id: str | None = None,
        visible: bool = True,
        foreground: bool = True,
        lease_seconds: int = 90,
    ) -> dict[str, Any]:
        requested = self._clean_surface_id(surface_id) or self._surface_id
        lease = max(15, min(300, int(lease_seconds)))
        result = self.client.surface_register(
            surface_id=requested,
            visible=bool(visible),
            foreground=bool(foreground),
            lease_seconds=lease,
        )
        payload = dict(result or {})
        resolved = self._clean_surface_id(
            payload.get("surface_id") or payload.get("id")
        )
        if resolved:
            self._surface_id = resolved
        return _json_safe(payload)

    def surface_renew(
        self,
        *,
        surface_id: str | None = None,
        visible: bool | None = None,
        foreground: bool | None = None,
        activity: str = "heartbeat",
    ) -> dict[str, Any]:
        resolved = self._clean_surface_id(surface_id) or self._surface_id
        result = self.client.surface_renew(
            surface_id=resolved,
            visible=visible,
            foreground=foreground,
            activity=str(activity or "heartbeat").lower() in {
                "activity",
                "foreground",
                "interaction",
                "wake",
            },
        )
        payload = dict(result or {})
        returned = self._clean_surface_id(
            payload.get("surface_id") or payload.get("id")
        )
        if returned:
            self._surface_id = returned
        return _json_safe(payload)

    def surface_disconnect(
        self,
        *,
        surface_id: str | None = None,
    ) -> dict[str, Any]:
        resolved = self._clean_surface_id(surface_id) or self._surface_id
        result = self.client.surface_disconnect(surface_id=resolved)
        if resolved == self._surface_id:
            self._surface_id = None
        return _json_safe(dict(result or {}))

    def surface_wake(
        self,
        *,
        surface_id: str | None = None,
    ) -> dict[str, Any]:
        resolved = self._clean_surface_id(surface_id) or self._surface_id
        return _json_safe(
            dict(self.client.surface_wake(surface_id=resolved) or {})
        )

    def lifecycle_status(
        self,
    ) -> dict[str, Any]:
        return _json_safe(dict(self.client.lifecycle_status() or {}))

    def character_state(
        self,
        *,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        state = (
            self.client
            .state()
        )

        character = dict(
            state.get(
                "mary",
                {},
            )
            or {}
        )

        if runtime_status:
            character[
                "runtime_status"
            ] = runtime_status

        return _json_safe(
            character
        )

    def dashboard_state(
        self,
        *,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        """Return the canonical Mary Core dashboard with mobile metadata.

        Remote mobile is a presentation surface only. Relationship, memory,
        personality, agency, growth, retrieval, perception, and other Mary
        state are projected from the authoritative Core dashboard rather than
        reconstructed by the mobile proxy.
        """

        state = (
            self.client
            .state()
        )

        conversation = (
            self.client
            .conversation_status()
        )

        payload = dict(
            self.client.dashboard()
            or {}
        )

        # The PWA's top-level ``character`` field is a presentation shape and
        # intentionally replaces Core's character-system projection below.
        # Preserve only the bounded Sourcebook inventory count needed by the
        # experience projector; never forward authored evidence or source text.
        sourcebook = dict(
            dict(
                state.get(
                    "character",
                    {},
                )
                or {}
            ).get(
                "sourcebook",
                {},
            )
            or {}
        )
        if not sourcebook:
            sourcebook = dict(
                payload.get(
                    "character_sourcebook",
                    {},
                )
                or {}
            )
        payload[
            "character_sourcebook"
        ] = _character_sourcebook_inventory(
            sourcebook
        )

        # Preserve the current PWA character shape and allow the presentation
        # layer to expose its temporary runtime status without changing Mary.
        payload[
            "character"
        ] = self.character_state(
            runtime_status=runtime_status,
        )

        # Conversation state is session-sensitive. Prefer the dedicated Core
        # conversation projection while retaining the dashboard value if a
        # lightweight/fake client omits it.
        payload[
            "engagement"
        ] = conversation.get(
            "engagement",
            payload.get(
                "engagement",
                {},
            ),
        )

        payload[
            "realtime"
        ] = conversation.get(
            "realtime",
            payload.get(
                "realtime",
                {},
            ),
        )

        # Keep current Core node state fresh when the state endpoint provides
        # it. Nodes remain capabilities; they never own Mary state.
        if state.get(
            "nodes"
        ) is not None:
            payload[
                "nodes"
            ] = state.get(
                "nodes",
                payload.get(
                    "nodes",
                    {},
                ),
            )

        # These fields describe the client surface and Core connection only.
        # They are deliberately layered onto, not substituted for, Mary state.
        payload[
            "mobile"
        ] = {
            "protocol": MOBILE_PROTOCOL_VERSION,
            "surface": "pwa",
            "authority": "remote_mary_core",
            "conversation_id": self._conversation_id,
        }

        payload[
            "core"
        ] = state.get(
            "core",
            {},
        )

        payload[
            "ecosystem"
        ] = self.ecosystem_state()

        return _json_safe(
            payload
        )

    def ecosystem_state(
        self,
    ) -> dict[str, Any]:
        workspace = getattr(
            self.client,
            "workspace",
            None,
        )

        if not callable(
            workspace
        ):
            return {}

        try:
            return _json_safe(
                workspace()
            )

        except Exception:
            return {}

    def last_turn_trace(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            return _json_safe(
                self._last_trace
            )

    def chat(
        self,
        text: str,
        *,
        conversation_id: str | None = None,
        voice_input: bool = False,
    ) -> dict[str, Any]:
        value = str(
            text
            or ""
        ).strip()

        if not value:
            raise ValueError(
                "Message text cannot be empty."
            )

        with self._lock:
            if self._busy:
                raise RuntimeError(
                    "Mary is already processing a message."
                )

            self._busy = True

        resolved_conversation_id = (
            _clean_conversation_id(
                conversation_id
                or self._conversation_id
            )
        )

        self._conversation_id = (
            resolved_conversation_id
        )

        started = monotonic()

        try:
            response = (
                self.client
                .turn(
                    value,
                    conversation_id=resolved_conversation_id,
                    voice_input=bool(
                        voice_input
                    ),
                )
            )

            elapsed = (
                monotonic()
                - started
            )

            provenance = dict(
                response.provenance
                or {}
            )
            display_hints = dict(
                response.display_hints
                or {}
            )
            raw_timings = dict(
                display_hints.get(
                    "timings",
                    {},
                )
                or {}
            )
            timings: dict[str, float] = {}
            for name in (
                "context_ms",
                "intent_ms",
                "reasoning_ms",
                "reflection_ms",
                "response_select_ms",
                "cognition_total_ms",
                "pipeline_ms",
            ):
                try:
                    duration = float(raw_timings[name])
                except (KeyError, TypeError, ValueError):
                    continue
                if duration >= 0.0:
                    timings[name] = round(
                        min(duration, 86_400_000.0),
                        2,
                    )
            timings[
                "worker_total_ms"
            ] = round(
                min(elapsed * 1000.0, 86_400_000.0),
                2,
            )

            def safe_identifier(value: Any, limit: int = 128) -> str:
                candidate = str(value or "").strip()[:limit]
                return (
                    candidate
                    if _SAFE_TRACE_IDENTIFIER.fullmatch(candidate)
                    else ""
                )

            safe_attempts: list[dict[str, str]] = []
            for raw in list(provenance.get("provider_attempts", []) or [])[:12]:
                if not isinstance(raw, dict):
                    continue
                safe_attempts.append({
                    "provider": safe_identifier(raw.get("provider"), 64),
                    "status": safe_identifier(raw.get("status"), 32),
                })
            lane = safe_identifier(
                dict(provenance.get("conversation_lane", {}) or {}).get("lane"),
                32,
            )

            trace = {
                "request_id": safe_identifier(
                    getattr(response, "request_id", ""),
                ),
                "turn_id": safe_identifier(response.turn_id),
                "elapsed": round(
                    max(0.0, min(elapsed, 86_400.0)),
                    6,
                ),
                "provider": safe_identifier(provenance.get("provider"), 64),
                "model": safe_identifier(provenance.get("model"), 128),
                "finish_reason": safe_identifier(
                    provenance.get("finish_reason"),
                    64,
                ),
                "route": safe_identifier(provenance.get("route"), 64),
                "provider_attempts": safe_attempts,
                "timings": timings,
                "authority": "remote_mary_core",
                "device_id": self.client.device_id,
            }

            if lane:
                trace[
                    "mobile"
                ] = {
                    "lane": lane,
                }

            with self._lock:
                self._last_trace = trace
                performance_packet = dict((response.display_hints or {}).get("performance_packet", {}) or {})
                delivery = dict((response.display_hints or {}).get("delivery_plan", {}) or {})
                self._last_feedback_context = {
                    "user_text": value,
                    "assistant_text": str(response.response or ""),
                    "source_kind": "creator_turn",
                    "input_authority": "creator",
                    "provider": str(trace.get("provider") or "unknown"),
                    "model": str(trace.get("model") or "unknown"),
                    "conversation_mode": str(
                        getattr(response, "effective_mode", "adaptive")
                        or "adaptive"
                    ),
                    "performance_context": str(performance_packet.get("social_context") or "private"),
                    "character_patterns": list(dict(delivery.get("metadata", {}) or {}).get("performer_patterns", []) or [])[:12],
                    "turn_id": str(response.turn_id or ""),
                }

            conversation = dict(
                response.conversation_state
                or {}
            )

            voice_status = dict(
                self.speech
                .status()
                .get(
                    "tts",
                    {},
                )
                or {}
            )

            return _json_safe(
                {
                    "text": response.response,
                    "canonical_text": response.response,
                    "avatar": {},
                    "voice": {
                        **voice_status,
                        "enabled": True,
                        "status": "ready",
                        "spoken_text": response.response,
                        "delivery_plan": dict(
                            response.display_hints.get(
                                "delivery_plan",
                                {},
                            )
                            or {}
                        ),
                        "performance_packet": dict(
                            response.display_hints.get(
                                "performance_packet",
                                {},
                            )
                            or {}
                        ),
                        "device_fallback": True,
                    },
                    "runtime": {
                        "turn_id": response.turn_id,
                        "conversation_id": resolved_conversation_id,
                        "elapsed": elapsed,
                        "success": True,
                        "trace": trace,
                        "turn_mind": dict(
                            response.display_hints.get(
                                "dialogue_plan",
                                {},
                            )
                            or {}
                        ),
                        "delivery_plan": dict(
                            response.display_hints.get(
                                "delivery_plan",
                                {},
                            )
                            or {}
                        ),
                        "performance_packet": dict(
                            response.display_hints.get(
                                "performance_packet",
                                {},
                            )
                            or {}
                        ),
                    },
                    "character": self.character_state(
                        runtime_status="idle"
                    ),
                    "engagement": conversation.get(
                        "engagement",
                        {},
                    ),
                    "growth": (
                        self.client
                        .growth_status()
                    ),
                    "realtime": conversation.get(
                        "realtime",
                        {},
                    ),
                    "dashboard": self.dashboard_state(
                        runtime_status="idle"
                    ),
                    "state_changes": (
                        response.state_changes
                    ),
                }
            )

        except MaryProtocolError as exc:
            with self._lock:
                self._last_trace = {
                    "request_id": str(exc.request_id or "")[:128],
                    "outcome": "failure",
                    "failure_kind": (
                        "core_http_failure"
                        if exc.status_code is not None
                        else "upstream_disconnect"
                    ),
                    "error_type": type(exc).__name__,
                    "authority": "remote_mary_core",
                    "device_id": self.client.device_id,
                }
            raise

        finally:
            with self._lock:
                self._busy = False

    def voice_status(
        self,
    ) -> dict[str, Any]:
        return _json_safe(
            self.speech.status()
        )

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

    def bridge_call(
        self,
        method: str,
        args: list[Any] | None = None,
    ) -> Any:
        name = str(
            method
            or ""
        ).strip()

        if name == "getStatus":
            return self.status()

        if name in {
            "getAvatarState",
            "getCharacterState",
        }:
            return self.character_state()

        if name == "getDashboardState":
            return self.dashboard_state()

        if name == "getLastTurnTrace":
            return self.last_turn_trace()

        if name == "getMobileVoiceStatus":
            return self.voice_status()

        if name == "getConversationEngagement":
            return (
                self.client
                .conversation_status()
                .get(
                    "engagement",
                    {},
                )
            )

        if name == "getGrowthState":
            return (
                self.client
                .growth_status()
            )

        if name == "getRealtimeState":
            return (
                self.client
                .conversation_status()
                .get(
                    "realtime",
                    {},
                )
            )

        if name == "getNodeState":
            return (
                self.client
                .nodes()
            )

        if name == "getEcosystemState":
            return self.ecosystem_state()

        if name == "getConversationContext":
            return {
                "conversation_id": self._conversation_id,
                "authority": "remote_mary_core",
            }

        if name == "setConversationId":
            values = list(
                args
                or []
            )

            self._conversation_id = (
                _clean_conversation_id(
                    values[0]
                    if values
                    else "creator-primary"
                )
            )

            return {
                "conversation_id": self._conversation_id,
                "authority": "remote_mary_core",
            }

        if name == "getPerformanceContext":
            return self.client.runtime_action(
                "performance.context.status"
            )

        if name == "setPerformanceContext":
            values = list(args or [])
            mode = str(values[0] if values else "private")
            return self.client.runtime_action(
                "performance.context.set",
                {"mode": mode},
            )

        if name == "personalSearch":
            values = list(
                args
                or []
            )

            query = str(
                values[0]
                if values
                else ""
            ).strip()

            if not query:
                raise ValueError(
                    "Search query cannot be empty."
                )

            limit = max(
                1,
                min(
                    12,
                    int(
                        values[1]
                        if len(values) > 1
                        else 8
                    ),
                ),
            )

            route = (
                self.client
                .route_capability(
                    "personal_search"
                )
            )

            if not route.get(
                "available"
            ):
                return {
                    "ok": False,
                    "results": [],
                    "status": "no_capable_node",
                    "error": (
                        "No connected device currently "
                        "provides PersonalSearch."
                    ),
                    "route": route,
                }

            dispatched = (
                self.client
                .dispatch_capability_task(
                    "personal_search",
                    (
                        "Search approved personal files for: "
                        f"{query}"
                    ),
                    {
                        "query": query,
                        "limit": limit,
                    },
                )
            )

            task = dict(
                dispatched.get(
                    "task",
                    {},
                )
                or {}
            )

            task_id = str(
                task.get(
                    "task_id"
                )
                or ""
            )

            deadline = (
                monotonic()
                + 12.0
            )

            while (
                task_id
                and monotonic() < deadline
            ):
                current = (
                    self.client
                    .capability_task_status(
                        task_id
                    )
                )

                task = dict(
                    current.get(
                        "task",
                        {},
                    )
                    or {}
                )

                status = str(
                    task.get(
                        "status"
                    )
                    or ""
                ).lower()

                if status == "completed":
                    result = dict(
                        task.get(
                            "result",
                            {},
                        )
                        or {}
                    )

                    items = list(
                        result.get(
                            "items",
                            [],
                        )
                        or []
                    )

                    return {
                        "ok": True,
                        "results": items,
                        "count": int(
                            result.get(
                                "count",
                                len(items),
                            )
                            or len(items)
                        ),
                        "task_id": task_id,
                        "status": status,
                        "privacy": result.get(
                            "privacy",
                            "device-sanitized results",
                        ),
                        "selected_node_id": (
                            task.get(
                                "selected_node_id"
                            )
                        ),
                    }

                if status in {
                    "rejected",
                    "failed",
                    "expired",
                }:
                    return {
                        "ok": False,
                        "results": [],
                        "task_id": task_id,
                        "status": status,
                        "error": str(
                            task.get(
                                "error"
                            )
                            or "PersonalSearch did not complete."
                        ),
                        "selected_node_id": (
                            task.get(
                                "selected_node_id"
                            )
                        ),
                    }

                sleep(
                    0.25
                )

            return {
                "ok": True,
                "results": [],
                "task_id": task_id,
                "status": "pending",
                "pending": True,
                "selected_node_id": (
                    task.get(
                        "selected_node_id"
                    )
                ),
                "message": (
                    "Search was queued on the selected "
                    "device and is still running."
                ),
            }

        if name == "setConversationMode":
            return (
                self.client
                .runtime_action(
                    "conversation.set_mode",
                    {
                        "mode": str(
                            args[0]
                            if args
                            else "adaptive"
                        )
                    },
                )
            )

        if name == "beginConversationSession":
            values = list(
                args
                or []
            )

            return (
                self.client
                .runtime_action(
                    "conversation.begin_session",
                    {
                        "mode": str(
                            values[0]
                            if values
                            else "engaged"
                        ),
                        "turns": int(
                            values[1]
                            if len(values) > 1
                            else 8
                        ),
                    },
                )
            )

        if name == "endConversationSession":
            return (
                self.client
                .runtime_action(
                    "conversation.end_session"
                )
            )

        workspace_actions = {
            "addCommandItem": lambda values: (
                "command.add",
                {
                    "title": str(
                        values[0]
                        if values
                        else ""
                    ),
                    "kind": str(
                        values[1]
                        if len(values) > 1
                        else "task"
                    ),
                },
            ),
            "updateCommandStatus": lambda values: (
                "command.update",
                {
                    "item_id": str(
                        values[0]
                    ),
                    "status": str(
                        values[1]
                    ),
                },
            ),
            "startFocus": lambda values: (
                "focus.start",
                {
                    "minutes": int(
                        values[0]
                    ),
                    "task": str(
                        values[1]
                        if len(values) > 1
                        else ""
                    ),
                },
            ),
            "stopFocus": lambda values: (
                "focus.stop",
                {},
            ),
            "createStudyProject": lambda values: (
                "study.create_project",
                {
                    "title": str(
                        values[0]
                    ),
                    "objective": str(
                        values[1]
                        if len(values) > 1
                        else ""
                    ),
                },
            ),
            "addStudyCard": lambda values: (
                "study.add_card",
                {
                    "project_id": str(
                        values[0]
                    ),
                    "prompt": str(
                        values[1]
                    ),
                    "answer": str(
                        values[2]
                    ),
                },
            ),
            "reviewStudyCard": lambda values: (
                "study.review_card",
                {
                    "project_id": str(
                        values[0]
                    ),
                    "card_id": str(
                        values[1]
                    ),
                    "score": int(
                        values[2]
                    ),
                },
            ),
            "markNoticeRead": lambda values: (
                "inbox.mark_read",
                {
                    "notice_id": str(
                        values[0]
                    ),
                    "read": True,
                },
            ),
            "createResearchThread": lambda values: (
                "research.create_thread",
                {
                    "title": str(
                        values[0]
                    ),
                    "question": str(
                        values[1]
                        if len(values) > 1
                        else ""
                    ),
                },
            ),
        }

        if name in workspace_actions:
            values = list(
                args
                or []
            )

            action, payload = (
                workspace_actions[
                    name
                ](
                    values
                )
            )

            return (
                self.client
                .workspace_action(
                    action,
                    payload,
                )
            )

        if name == "presencePulse":
            values = list(args or [])
            surface_visible = bool(values[0]) if values else True
            focus_active = bool(values[1]) if len(values) > 1 else False
            payload = dict(
                self.client.runtime_action(
                    "presence.pulse",
                    {
                        "surface": "mobile",
                        "surface_visible": surface_visible,
                        "focus_active": focus_active,
                        "conversation_id": self._conversation_id,
                    },
                )
                or {}
            )
            if not bool(payload.get("speak") or payload.get("spoke")):
                return payload

            response_text = str(payload.get("response") or payload.get("text") or "")
            hints = dict(payload.get("display_hints") or {})
            delivery = dict(hints.get("delivery_plan") or {})
            packet = dict(hints.get("performance_packet") or payload.get("performance_packet") or {})
            provenance = dict(payload.get("provenance") or {})
            candidate_context = str(payload.get("presence_context") or "").strip()
            if not candidate_context:
                candidate_context = str(
                    dict(payload.get("candidate") or {}).get("summary")
                    or payload.get("initiative_kind")
                    or "Mary initiative"
                )
            with self._lock:
                self._last_feedback_context = {
                    "user_text": "",
                    "context_text": candidate_context[:4000],
                    "assistant_text": response_text,
                    "source_kind": "mary_initiative",
                    "input_authority": str(payload.get("authority") or "environment_context_only"),
                    "provider": str(provenance.get("provider") or "unknown"),
                    "model": str(provenance.get("model") or "unknown"),
                    "conversation_mode": str(
                        dict(payload.get("conversation_state") or {}).get("engagement", {}).get("mode")
                        or "adaptive"
                    ),
                    "performance_context": str(packet.get("social_context") or "private"),
                    "character_patterns": list(dict(delivery.get("metadata") or {}).get("performer_patterns", []) or [])[:12],
                    "turn_id": str(payload.get("turn_id") or ""),
                }
            voice_status = dict(self.speech.status().get("tts", {}) or {})
            return _json_safe({
                **payload,
                "text": response_text,
                "voice": {
                    **voice_status,
                    "enabled": True,
                    "status": "ready",
                    "spoken_text": response_text,
                    "delivery_plan": delivery,
                    "performance_packet": packet,
                    "device_fallback": True,
                },
                "runtime": {
                    "turn_id": str(payload.get("turn_id") or ""),
                    "conversation_id": self._conversation_id,
                    "initiative": True,
                    "delivery_plan": delivery,
                    "performance_packet": packet,
                    "turn_mind": dict(hints.get("dialogue_plan") or {}),
                },
            })

        if name == "getTrainingFeedbackState":
            return self.client.runtime_action(
                "training.feedback.status"
            )

        if name == "recordResponseFeedback":
            values = list(args or [])
            rating = str(values[0] if values else "neutral")
            tags = list(
                values[1]
                if len(values) > 1 and isinstance(values[1], list)
                else []
            )
            note = str(values[2] if len(values) > 2 else "")
            chosen_text = str(values[3] if len(values) > 3 else "")
            with self._lock:
                context = dict(self._last_feedback_context)
            if not context:
                raise ValueError(
                    "No completed mobile turn is available to rate."
                )
            return self.client.runtime_action(
                "training.feedback.record",
                {
                    **context,
                    "rating": rating,
                    "tags": tags,
                    "note": note,
                    "chosen_text": chosen_text,
                },
            )

        if name == "reportSpeechStarted":
            values = list(
                args
                or []
            )

            return (
                self.client
                .runtime_action(
                    "realtime.speech_started",
                    {
                        "turn_id": str(
                            values[0]
                            if values
                            else ""
                        )
                    },
                )
            )

        if name in {
            "reportSpeechEnded",
            "reportSpeechFinished",
        }:
            values = list(
                args
                or []
            )

            return (
                self.client
                .runtime_action(
                    "realtime.speech_ended",
                    {
                        "reason": str(
                            values[0]
                            if values
                            else "speech_finished"
                        )
                    },
                )
            )

        if name == "reportSpeechInterrupted":
            values = list(
                args
                or []
            )

            return (
                self.client
                .runtime_action(
                    "realtime.interrupt",
                    {
                        "reason": str(
                            values[0]
                            if values
                            else "client_barge_in"
                        )
                    },
                )
            )

        raise KeyError(
            "Bridge method is not available "
            f"in remote-core mobile mode: {name}"
        )

    def close(
        self,
    ) -> bool:
        # A frontend disconnect must never shut down
        # the authoritative Core.
        return True


class MaryMobileRuntime:
    """Thread-safe transport facade over one canonical MaryApplication."""

    def __init__(
        self,
        application: MaryApplication | None = None,
    ) -> None:
        self.application = (
            application
            or create_application(
                name="mary_mobile"
            )
        )

        # Canonical ecosystem ownership lives on MaryApplication.
        # Mobile must reuse it rather than constructing another wrapper.
        self.ecosystem = (
            self.application
            .ecosystem
        )

        self.creative_workspace = (
            CreativeWorkspaceManager()
        )

        self.speech = (
            MobileSpeechService()
        )

        data_root = Path(
            self.application
            .mary
            .config
            .paths
            .data
        )

        self.voice_lab = (
            VoiceLabStore(
                data_root
                / "voice"
                / "voice_lab.json"
            )
        )

        self.speech.apply_voice_profile(
            self.voice_lab.selected()
        )

        self._lock = (
            RLock()
        )

        self._busy = False

        self._last_trace: dict[
            str,
            Any,
        ] = {}

        self._last_feedback_context: dict[
            str,
            Any,
        ] = {}

        self._conversation_id = (
            _clean_conversation_id(
                os.getenv(
                    "MARY_CONVERSATION_ID",
                    "creator-primary",
                )
            )
        )

        try:
            self.application.mary.avatar.ready()

        except Exception:
            pass

    @staticmethod
    def _local_lifecycle_unavailable() -> None:
        """Local legacy runtime has no Core surface lifecycle authority."""
        raise RuntimeError(
            "Surface lifecycle requires a configured remote Mary Core."
        )

    def surface_register(self, **_: Any) -> dict[str, Any]:
        self._local_lifecycle_unavailable()

    def surface_renew(self, **_: Any) -> dict[str, Any]:
        self._local_lifecycle_unavailable()

    def surface_disconnect(self, **_: Any) -> dict[str, Any]:
        self._local_lifecycle_unavailable()

    def surface_wake(self, **_: Any) -> dict[str, Any]:
        self._local_lifecycle_unavailable()

    def lifecycle_status(self) -> dict[str, Any]:
        return {
            "supported": False,
            "reason": "remote_mary_core_required",
        }

    @property
    def busy(
        self,
    ) -> bool:
        with self._lock:
            return self._busy

    def status(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            mary_status = dict(
                self.application
                .mary
                .status()
                or {}
            )

            cognition = dict(
                mary_status.get(
                    "cognition",
                    {},
                )
                or {}
            )

            environment = dict(
                self.application
                .mary
                .runtime_environment
                .snapshot()
                or {}
            )

            return _json_safe(
                {
                    "name": mary_status.get(
                        "name",
                        "Mary",
                    ),
                    "provider": cognition.get(
                        "llm",
                        "runtime",
                    ),
                    "model": cognition.get(
                        "model",
                        "MaryV2",
                    ),
                    "busy": self._busy,
                    "conversation": {
                        "state": (
                            "thinking"
                            if self._busy
                            else "idle"
                        )
                    },
                    "voice": {
                        **dict(
                            self.speech
                            .status()
                            .get(
                                "tts",
                                {},
                            )
                            or {}
                        ),
                        "mode": (
                            "server_preferred_with_device_fallback"
                        ),
                    },
                    "speech_to_text": {
                        **dict(
                            self.speech
                            .status()
                            .get(
                                "stt",
                                {},
                            )
                            or {}
                        ),
                        "mode": (
                            "server_upload_with_browser_fallback"
                        ),
                    },
                    "mobile": {
                        "protocol": MOBILE_PROTOCOL_VERSION,
                        "conversation_id": self._conversation_id,
                        "host_type": environment.get(
                            "host_type",
                            "unknown",
                        ),
                        "effective_conversation_route": (
                            environment.get(
                                "effective_conversation_route",
                                [],
                            )
                        ),
                    },
                    "engagement": (
                        self.application
                        .mary
                        .engagement
                        .status()
                    ),
                    "growth": (
                        self.application
                        .mary
                        .growth
                        .status()
                    ),
                    "realtime": (
                        self.application
                        .mary
                        .realtime
                        .status()
                    ),
                    "nodes": (
                        self.application
                        .mary
                        .node_registry
                        .snapshot()
                    ),
                    "retrieval": (
                        self.application
                        .mary
                        .mind
                        .retrieval
                        .status()
                    ),
                    "perception": (
                        self.application
                        .mary
                        .perception_director
                        .snapshot()
                    ),
                    "training_feedback": (
                        self.application
                        .mary
                        .training_feedback
                        .status()
                    ),
                }
            )

    def avatar_state(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return _json_safe(
                    self.application
                    .mary
                    .avatar
                    .state
                    .to_dict()
                )

            except Exception:
                return {}

    def character_state(
        self,
        *,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            resolved_status = (
                runtime_status
                or (
                    "thinking"
                    if self._busy
                    else "idle"
                )
            )

            return _json_safe(
                self.application
                .mary
                .live_state(
                    runtime_status=resolved_status
                )
            )

    def dashboard_state(
        self,
        *,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            resolved_status = (
                runtime_status
                or (
                    "thinking"
                    if self._busy
                    else "idle"
                )
            )

            payload = (
                build_desktop_dashboard_state(
                    self.application.mary,
                    runtime_status=resolved_status,
                )
            )

            sourcebook = getattr(
                self.application.mary,
                "character_sourcebook",
                None,
            )
            try:
                sourcebook_state = (
                    sourcebook.snapshot()
                    if callable(
                        getattr(
                            sourcebook,
                            "snapshot",
                            None,
                        )
                    )
                    else {}
                )
            except Exception:
                sourcebook_state = {}
            payload[
                "character_sourcebook"
            ] = _character_sourcebook_inventory(
                sourcebook_state
            )

            payload[
                "ecosystem"
            ] = (
                self.ecosystem
                .snapshot()
            )

            try:
                payload[
                    "mind"
                ] = (
                    self.application
                    .mary
                    .mind
                    .status()
                )

            except Exception as exc:
                payload[
                    "mind"
                ] = {
                    "enabled": False,
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                }

            payload[
                "mobile"
            ] = {
                "protocol": MOBILE_PROTOCOL_VERSION,
                "surface": "pwa",
                "authority": "local_development_runtime",
                "conversation_id": self._conversation_id,
            }

            payload[
                "engagement"
            ] = (
                self.application
                .mary
                .engagement
                .status()
            )

            payload[
                "growth"
            ] = (
                self.application
                .mary
                .growth
                .status()
            )

            payload[
                "voice_lab"
            ] = (
                self.voice_lab
                .public_state()
            )

            payload[
                "realtime"
            ] = (
                self.application
                .mary
                .realtime
                .status()
            )

            payload[
                "nodes"
            ] = (
                self.application
                .mary
                .node_registry
                .snapshot()
            )

            payload[
                "retrieval"
            ] = (
                self.application
                .mary
                .mind
                .retrieval
                .status()
            )

            payload[
                "perception"
            ] = (
                self.application
                .mary
                .perception_director
                .snapshot()
            )

            payload[
                "training_feedback"
            ] = (
                self.application
                .mary
                .training_feedback
                .status()
            )

            return _json_safe(
                payload
            )

    def ecosystem_state(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            return _json_safe(
                self.ecosystem
                .snapshot()
            )

    def mind_status(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return _json_safe(
                    self.application
                    .mary
                    .mind
                    .status()
                )

            except Exception as exc:
                return {
                    "enabled": False,
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                }

    def last_turn_trace(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            return _json_safe(
                self._last_trace
                or self.ecosystem.metrics.last_turn()
                or {}
            )

    def chat(
        self,
        text: str,
        *,
        conversation_id: str | None = None,
        voice_input: bool = False,
    ) -> dict[str, Any]:
        value = str(
            text
            or ""
        ).strip()

        if not value:
            raise ValueError(
                "Message text cannot be empty."
            )

        if len(
            value
        ) > 32_000:
            raise ValueError(
                "Message is too long for the mobile transport."
            )

        with self._lock:
            if self._busy:
                raise RuntimeError(
                    "Mary is already processing a message."
                )

            self._busy = True

        started = monotonic()

        try:
            lane = (
                classify_conversation_lane(
                    value
                )
            )

            pipeline_started = (
                monotonic()
            )

            resolved_conversation_id = (
                _clean_conversation_id(
                    conversation_id
                    or self._conversation_id
                )
            )

            self._conversation_id = (
                resolved_conversation_id
            )

            result = (
                self.application
                .run(
                    value,
                    metadata={
                        "surface": "mobile",
                        "transport": "http",
                        "conversation_id": resolved_conversation_id,
                        "voice_input": bool(
                            voice_input
                        ),
                    },
                )
            )

            pipeline_ms = (
                monotonic()
                - pipeline_started
            ) * 1000.0

            if not result.success:
                raise RuntimeError(
                    result.error
                    or "Mary's pipeline did not complete."
                )

            response_text = str(
                result.output
                or ""
            )

            mary = (
                self.application
                .mary
            )

            avatar_started = (
                monotonic()
            )

            delivery_plan: dict[
                str,
                Any,
            ] = {}
            performance_packet: dict[str, Any] = {}

            try:
                values = dict(
                    getattr(
                        result,
                        "metadata",
                        {},
                    ).get(
                        "pipeline_values",
                        {},
                    )
                    or {}
                )

                cycle = (
                    values.get(
                        "cognitive_cycle"
                    )
                )

                cycle_metadata = dict(
                    getattr(
                        cycle,
                        "metadata",
                        {},
                    )
                    or {}
                )

                delivery_plan = dict(
                    cycle_metadata.get(
                        "delivery_plan",
                        {},
                    )
                    or {}
                )
                performance_packet = dict(
                    cycle_metadata.get(
                        "performance_packet",
                        {},
                    )
                    or {}
                )

                mary.avatar.sync_emotion()

                avatar = (
                    mary.avatar
                    .controller
                    .present(
                        text=response_text,
                        speaking=False,
                        metadata={
                            "surface": "mobile",
                            "delivery_plan": delivery_plan,
                        },
                    )
                    .to_dict()
                )

            except Exception:
                try:
                    avatar = (
                        mary.avatar
                        .state
                        .to_dict()
                    )

                except Exception:
                    avatar = {}

            avatar_ms = (
                monotonic()
                - avatar_started
            ) * 1000.0

            worker_total_ms = (
                monotonic()
                - started
            ) * 1000.0

            voice_status = dict(
                self.speech
                .status()
                .get(
                    "tts",
                    {},
                )
                or {}
            )

            trace = build_turn_trace(
                result,
                pipeline_ms=pipeline_ms,
                avatar_ms=avatar_ms,
                voice_payload={
                    "enabled": bool(
                        voice_status.get(
                            "enabled",
                            True,
                        )
                    ),
                    "provider": (
                        voice_status.get(
                            "provider"
                        )
                        or "device_fallback"
                    ),
                    "status": (
                        "deferred_mobile_playback"
                    ),
                },
                worker_total_ms=worker_total_ms,
            )

            trace.setdefault(
                "mobile",
                {},
            )[
                "lane"
            ] = getattr(
                lane.lane,
                "value",
                str(
                    lane.lane
                ),
            )

            self.ecosystem.record_turn(
                elapsed=result.elapsed,
                trace=trace,
            )

            with self._lock:
                self._last_trace = trace

                engagement_status = (
                    mary.engagement
                    .status()
                )

                active_session = dict(
                    engagement_status.get(
                        "active_session",
                        {},
                    )
                    or {}
                )

                self._last_feedback_context = {
                    "user_text": value,
                    "assistant_text": response_text,
                    "source_kind": "creator_turn",
                    "input_authority": "creator",
                    "provider": str(
                        trace.get(
                            "provider"
                        )
                        or "unknown"
                    ),
                    "model": str(
                        trace.get(
                            "model"
                        )
                        or "unknown"
                    ),
                    "conversation_mode": str(
                        active_session.get(
                            "mode"
                        )
                        or engagement_status.get(
                            "mode"
                        )
                        or "adaptive"
                    ),
                    "performance_context": str(performance_packet.get("social_context") or "private"),
                    "character_patterns": list(dict(delivery_plan.get("metadata", {}) or {}).get("performer_patterns", []) or [])[:12],
                    "turn_id": str(
                        result.turn_id
                        or ""
                    ),
                }

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
                        "performance_packet": performance_packet,
                        "device_fallback": True,
                    },
                    "runtime": {
                        "turn_id": result.turn_id,
                        "conversation_id": resolved_conversation_id,
                        "elapsed": result.elapsed,
                        "success": True,
                        "trace": trace,
                        "turn_mind": dict(
                            getattr(
                                result,
                                "metadata",
                                {},
                            ).get(
                                "dialogue_plan",
                                {},
                            )
                            or {}
                        ),
                        "delivery_plan": dict(
                            delivery_plan
                            or {}
                        ),
                        "performance_packet": dict(
                            performance_packet
                            or {}
                        ),
                        "conversation_lane": getattr(
                            lane.lane,
                            "value",
                            str(
                                lane.lane
                            ),
                        ),
                    },
                    "character": self.character_state(
                        runtime_status="idle"
                    ),
                    "engagement": (
                        mary.engagement
                        .status()
                    ),
                    "growth": (
                        mary.growth
                        .status()
                    ),
                    "realtime": (
                        mary.realtime
                        .status()
                    ),
                    "dashboard": self.dashboard_state(
                        runtime_status="idle"
                    ),
                }
            )

        finally:
            with self._lock:
                self._busy = False

    def voice_status(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            return _json_safe(
                self.speech
                .status()
            )

    def synthesize_speech(
        self,
        text: str,
        *,
        user_text: str | None = None,
        delivery_plan: dict[str, Any] | None = None,
    ):
        return (
            self.speech
            .synthesize(
                text,
                user_text=user_text,
                delivery_plan=delivery_plan,
            )
        )

    def transcribe_audio(
        self,
        audio: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        mary = (
            self.application
            .mary
        )

        if not (
            mary.realtime
            .should_accept_audio_input(
                source="mobile_microphone"
            )
        ):
            return {
                "ok": False,
                "text": "",
                "suppressed": True,
                "reason": (
                    "anti_echo_while_mary_speaking"
                ),
            }

        mary.realtime.mark_transcribing(
            True,
            source="mobile_stt",
        )

        try:
            return (
                self.speech
                .transcribe(
                    audio,
                    filename=filename,
                    content_type=content_type,
                )
            )

        finally:
            mary.realtime.mark_transcribing(
                False,
                source="mobile_stt",
            )

    def _publish(
        self,
        event_type: PresenceEventType,
        summary: str,
        **metadata: Any,
    ) -> None:
        try:
            self.ecosystem.publish_workspace_event(
                event_type,
                summary,
                importance=float(
                    metadata.pop(
                        "importance",
                        0.55,
                    )
                ),
                metadata=(
                    metadata
                    or None
                ),
            )

        except Exception:
            pass

    def bridge_call(
        self,
        method: str,
        args: list[Any] | None = None,
    ) -> Any:
        """Implement the display-safe subset used by the shared desktop UI."""

        name = str(
            method
            or ""
        ).strip()

        values = list(
            args
            or []
        )

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

            if name == "getConversationEngagement":
                return (
                    self.application
                    .mary
                    .engagement
                    .status()
                )

            if name == "getConversationContext":
                return {
                    "conversation_id": self._conversation_id,
                    "authority": "local_development_runtime",
                }

            if name == "setConversationId":
                self._conversation_id = (
                    _clean_conversation_id(
                        values[0]
                        if values
                        else "creator-primary"
                    )
                )

                return {
                    "conversation_id": self._conversation_id,
                    "authority": "local_development_runtime",
                }

            if name == "getPerformanceContext":
                return self.application.mary.performance_context.status()

            if name == "setPerformanceContext":
                return self.application.mary.performance_context.set_mode(
                    str(values[0] if values else "private")
                )

            if name == "setConversationMode":
                return (
                    self.application
                    .mary
                    .engagement
                    .set_mode(
                        str(
                            values[0]
                            if values
                            else "adaptive"
                        )
                    )
                )

            if name == "beginConversationSession":
                mode = str(
                    values[0]
                    if values
                    else "engaged"
                )

                turns = int(
                    values[1]
                    if len(values) > 1
                    else 8
                )

                self.application.mary.engagement.begin_session(
                    mode,
                    turns=turns,
                    reason="mobile_control",
                )

                return (
                    self.application
                    .mary
                    .engagement
                    .status()
                )

            if name == "endConversationSession":
                self.application.mary.engagement.end_session()

                return (
                    self.application
                    .mary
                    .engagement
                    .status()
                )

            if name == "getGrowthState":
                return (
                    self.application
                    .mary
                    .growth
                    .status()
                )

            if name == "getRealtimeState":
                return (
                    self.application
                    .mary
                    .realtime
                    .status()
                )

            if name == "getAttentionState":
                return (
                    self.application
                    .mary
                    .realtime
                    .attention
                    .snapshot()
                )

            if name == "getNodeState":
                return (
                    self.application
                    .mary
                    .node_registry
                    .snapshot()
                )

            if name == "getRetrievalState":
                return (
                    self.application
                    .mary
                    .mind
                    .retrieval
                    .status()
                )

            if name == "reportSpeechStarted":
                turn_id = str(
                    values[0]
                    if values
                    else ""
                ) or None

                self.application.mary.realtime.speech_started(
                    turn_id=turn_id,
                    source="mobile_client",
                )

                return (
                    self.application
                    .mary
                    .realtime
                    .status()
                )

            if name == "reportSpeechEnded":
                reason = str(
                    values[0]
                    if values
                    else "speech_finished"
                )

                self.application.mary.realtime.speech_ended(
                    reason=reason
                )

                return (
                    self.application
                    .mary
                    .realtime
                    .status()
                )

            if name == "reportSpeechInterrupted":
                reason = str(
                    values[0]
                    if values
                    else "client_barge_in"
                )

                self.application.mary.realtime.interrupt(
                    reason=reason,
                    by_source="mobile_client",
                )

                self.application.mary.realtime.speech_ended(
                    reason="interrupted"
                )

                return (
                    self.application
                    .mary
                    .realtime
                    .status()
                )

            if name == "rebuildSemanticVectors":
                limit = (
                    int(
                        values[0]
                    )
                    if values
                    else None
                )

                return (
                    self.application
                    .mary
                    .mind
                    .rebuild_vectors(
                        limit=limit
                    )
                )

            if name == "presencePulse":
                surface_visible = bool(values[0]) if values else True
                focus_active = bool(values[1]) if len(values) > 1 else False
                pulse = self.application.presence_pulse(
                    surface="mobile",
                    conversation_id=self._conversation_id,
                    device_id="mobile-local",
                    surface_visible=surface_visible,
                    focus_active=focus_active,
                )
                result = pulse.pop("pipeline_result", None)
                if not bool(pulse.get("spoke")) or result is None:
                    return _json_safe(pulse)

                response_text = str(result.output or "")
                pipeline_values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
                cycle = pipeline_values.get("cognitive_cycle")
                cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
                delivery = dict(cycle_metadata.get("delivery_plan", {}) or {})
                packet = dict(cycle_metadata.get("performance_packet", {}) or {})
                reasoning = getattr(cycle, "reasoning", None)
                reasoning_meta = dict(getattr(reasoning, "metadata", {}) or {})
                candidate = dict(pulse.get("candidate") or {})
                with self._lock:
                    self._last_feedback_context = {
                        "user_text": "",
                        "context_text": str(candidate.get("summary") or "Mary initiative")[:4000],
                        "assistant_text": response_text,
                        "source_kind": "mary_initiative",
                        "input_authority": "environment_context_only",
                        "provider": str(reasoning_meta.get("provider") or "local/system"),
                        "model": str(reasoning_meta.get("model") or "n/a"),
                        "conversation_mode": str(self.application.mary.engagement.status().get("mode") or "adaptive"),
                        "performance_context": str(packet.get("social_context") or "private"),
                        "character_patterns": list(dict(delivery.get("metadata") or {}).get("performer_patterns", []) or [])[:12],
                        "turn_id": str(result.turn_id or ""),
                    }
                voice_status = dict(self.speech.status().get("tts", {}) or {})
                return _json_safe({
                    **pulse,
                    "speak": True,
                    "spoke": True,
                    "text": response_text,
                    "response": response_text,
                    "turn_id": str(result.turn_id or ""),
                    "voice": {
                        **voice_status,
                        "enabled": True,
                        "status": "ready",
                        "spoken_text": response_text,
                        "delivery_plan": delivery,
                        "performance_packet": packet,
                        "device_fallback": True,
                    },
                    "runtime": {
                        "turn_id": str(result.turn_id or ""),
                        "conversation_id": self._conversation_id,
                        "initiative": True,
                        "delivery_plan": delivery,
                        "performance_packet": packet,
                    },
                })

            if name == "getTrainingFeedbackState":
                return (
                    self.application
                    .mary
                    .training_feedback
                    .status()
                )

            if name == "recordResponseFeedback":
                rating = str(
                    values[0]
                    if values
                    else "neutral"
                )

                tags = list(
                    values[1]
                    if (
                        len(values) > 1
                        and isinstance(
                            values[1],
                            list,
                        )
                    )
                    else []
                )

                note = str(
                    values[2]
                    if len(values) > 2
                    else ""
                )
                chosen_text = str(
                    values[3]
                    if len(values) > 3
                    else ""
                )

                with self._lock:
                    context = dict(
                        self._last_feedback_context
                    )

                if not context:
                    raise ValueError(
                        "No completed mobile turn is available to rate."
                    )

                record = (
                    self.application
                    .mary
                    .training_feedback
                    .record(
                        rating=rating,
                        tags=tags,
                        note=note,
                        chosen_text=chosen_text,
                        **context,
                    )
                )

                return {
                    "ok": True,
                    "id": record.id,
                    "status": (
                        self.application
                        .mary
                        .training_feedback
                        .status()
                    ),
                }

            if name == "getVoiceLab":
                return (
                    self.voice_lab
                    .public_state()
                )

            if name == "saveVoiceProfile":
                label = str(
                    values[0]
                    if values
                    else "Mary Voice"
                )

                voice_id = str(
                    values[1]
                    if len(values) > 1
                    else ""
                )

                settings = dict(
                    values[2]
                    if (
                        len(values) > 2
                        and isinstance(
                            values[2],
                            dict,
                        )
                    )
                    else VOICE_BASELINE
                )

                item = (
                    self.voice_lab
                    .save_profile(
                        label,
                        voice_id,
                        settings=settings,
                        select=True,
                    )
                )

                self.speech.apply_voice_profile(
                    item
                )

                return (
                    self.voice_lab
                    .public_state()
                )

            if name == "selectVoiceProfile":
                item = (
                    self.voice_lab
                    .select(
                        str(
                            values[0]
                        )
                    )
                )

                self.speech.apply_voice_profile(
                    item
                )

                return (
                    self.voice_lab
                    .public_state()
                )

            if name == "deleteVoiceProfile":
                self.voice_lab.delete(
                    str(
                        values[0]
                    )
                )

                self.speech.apply_voice_profile(
                    self.voice_lab.selected()
                )

                return (
                    self.voice_lab
                    .public_state()
                )

            if name == "resetVoiceBaseline":
                item = (
                    self.voice_lab
                    .selected()
                )

                if item is not None:
                    item = (
                        self.voice_lab
                        .save_profile(
                            str(
                                item.get(
                                    "label"
                                )
                                or "Mary Voice"
                            ),
                            str(
                                item.get(
                                    "voice_id"
                                )
                                or ""
                            ),
                            settings=dict(
                                VOICE_BASELINE
                            ),
                            profile_id=str(
                                item.get(
                                    "id"
                                )
                                or ""
                            ),
                            select=True,
                        )
                    )

                    self.speech.apply_voice_profile(
                        item
                    )

                return (
                    self.voice_lab
                    .public_state()
                )

            if name == "rebuildCognitiveReservoir":
                try:
                    count = int(
                        self.application
                        .mary
                        .mind
                        .rebuild_reservoir()
                    )

                    return {
                        "ok": True,
                        "records": count,
                        "status": self.mind_status(),
                    }

                except Exception as exc:
                    return {
                        "ok": False,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }

            if name == "addCommandItem":
                title = str(
                    values[0]
                    if values
                    else ""
                )

                kind = str(
                    values[1]
                    if len(values) > 1
                    else "task"
                )

                item = (
                    self.ecosystem
                    .command
                    .add(
                        title,
                        kind=kind
                        or "task",
                    )
                )

                self._publish(
                    PresenceEventType.COMMAND_CHANGED,
                    (
                        "Command Center added "
                        f"{item.get('title', '')}"
                    ),
                    item_id=item.get(
                        "id"
                    ),
                )

                return {
                    "ok": True,
                    "item": item,
                }

            if name == "updateCommandStatus":
                item = (
                    self.ecosystem
                    .command
                    .update(
                        str(
                            values[0]
                        ),
                        status=str(
                            values[1]
                        ),
                    )
                )

                self._publish(
                    PresenceEventType.COMMAND_CHANGED,
                    (
                        "Command Center updated "
                        f"{item.get('title', '')}"
                    ),
                    item_id=item.get(
                        "id"
                    ),
                    status=item.get(
                        "status"
                    ),
                )

                return {
                    "ok": True,
                    "item": item,
                }

            if name == "startFocus":
                minutes = int(
                    values[0]
                )

                task = str(
                    values[1]
                    if len(values) > 1
                    else ""
                )

                state = (
                    self.ecosystem
                    .focus
                    .start(
                        minutes,
                        task=task,
                    )
                )

                self._publish(
                    PresenceEventType.FOCUS_CHANGED,
                    (
                        f"Focus started for "
                        f"{minutes} minutes"
                    ),
                    active=True,
                    minutes=minutes,
                )

                return {
                    "ok": True,
                    "focus": state,
                }

            if name == "stopFocus":
                state = (
                    self.ecosystem
                    .focus
                    .stop()
                )

                self._publish(
                    PresenceEventType.FOCUS_CHANGED,
                    "Focus session stopped",
                    active=False,
                )

                return {
                    "ok": True,
                    "focus": state,
                }

            if name == "createStudyProject":
                project = (
                    self.ecosystem
                    .study
                    .create_project(
                        str(
                            values[0]
                        ),
                        objective=str(
                            values[1]
                            if len(values) > 1
                            else ""
                        ),
                    )
                )

                self._publish(
                    PresenceEventType.STUDY_CHANGED,
                    (
                        "Study project created: "
                        f"{project.get('title', '')}"
                    ),
                    project_id=project.get(
                        "id"
                    ),
                )

                return {
                    "ok": True,
                    "project": project,
                }

            if name == "addStudyCard":
                card = (
                    self.ecosystem
                    .study
                    .add_card(
                        str(
                            values[0]
                        ),
                        str(
                            values[1]
                        ),
                        str(
                            values[2]
                        ),
                    )
                )

                return {
                    "ok": True,
                    "card": card,
                }

            if name == "reviewStudyCard":
                card = (
                    self.ecosystem
                    .study
                    .review(
                        str(
                            values[0]
                        ),
                        str(
                            values[1]
                        ),
                        int(
                            values[2]
                        ),
                    )
                )

                return {
                    "ok": True,
                    "card": card,
                }

            if name == "personalSearch":
                return {
                    "ok": True,
                    "results": (
                        self.ecosystem
                        .search
                        .search(
                            str(
                                values[0]
                            )
                        )
                    ),
                }

            if name == "markNoticeRead":
                return bool(
                    self.ecosystem
                    .inbox
                    .mark_read(
                        str(
                            values[0]
                        ),
                        True,
                    )
                )

            if name == "createResearchThread":
                thread = (
                    self.ecosystem
                    .research
                    .create(
                        str(
                            values[0]
                        ),
                        question=str(
                            values[1]
                            if len(values) > 1
                            else ""
                        ),
                    )
                )

                return {
                    "ok": True,
                    "thread": thread,
                }

            if name == "playArcade":
                return {
                    "ok": True,
                    **(
                        self.ecosystem
                        .arcade
                        .play(
                            str(
                                values[0]
                            ),
                            str(
                                values[1]
                                if len(values) > 1
                                else ""
                            ),
                        )
                    ),
                }

            if name == "getIdleAction":
                focus_active = bool(
                    self.ecosystem
                    .focus
                    .snapshot()
                    .get(
                        "active"
                    )
                )

                return (
                    self.ecosystem
                    .presence
                    .idle_tick(
                        focus_active=focus_active
                    )
                )

            if name == "getYouTubeStatus":
                return (
                    self.ecosystem
                    .youtube
                    .status()
                )

            if name == "searchYouTube":
                try:
                    results = (
                        self.ecosystem
                        .youtube
                        .search(
                            str(
                                values[0]
                            )
                        )
                    )

                    return {
                        "ok": True,
                        "results": results,
                        "status": (
                            self.ecosystem
                            .youtube
                            .status()
                        ),
                    }

                except Exception as exc:
                    return {
                        "ok": False,
                        "error": str(
                            exc
                        ),
                        "results": [],
                        "status": (
                            self.ecosystem
                            .youtube
                            .status()
                        ),
                    }

            if name == "saveYouTubeToResearch":
                thread = (
                    self.ecosystem
                    .research
                    .create(
                        str(
                            values[0]
                            or "YouTube research"
                        ),
                        question=str(
                            values[1]
                            if len(values) > 1
                            else ""
                        ),
                    )
                )

                return {
                    "ok": True,
                    "thread": thread,
                }

            # Native-desktop-only surfaces remain explicit rather than pretending
            # the phone can launch local Windows applications or file pickers.
            if name in {
                "getIntegrationState"
            }:
                return {
                    "creative_apps": [],
                    "mobile_limited": True,
                }

            if name == "getCreativeWorkspaceState":
                try:
                    return (
                        self.creative_workspace
                        .status()
                    )

                except Exception as exc:
                    return {
                        "configured": False,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                        "files": [],
                    }

            if name == "readCreativeTextFile":
                try:
                    return {
                        "ok": True,
                        **(
                            self.creative_workspace
                            .read_text(
                                str(
                                    values[0]
                                    if values
                                    else ""
                                )
                            )
                        ),
                    }

                except Exception as exc:
                    return {
                        "ok": False,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }

            if name == "saveCreativeTextFile":
                try:
                    relative_path = str(
                        values[0]
                        if values
                        else ""
                    )

                    content = str(
                        values[1]
                        if len(values) > 1
                        else ""
                    )

                    result = (
                        self.creative_workspace
                        .save_text(
                            relative_path,
                            content,
                        )
                    )

                    self._publish(
                        PresenceEventType.CREATIVE_CHANGED,
                        (
                            "Creative text saved from mobile: "
                            f"{relative_path}"
                        ),
                        relative_path=relative_path[
                            :240
                        ],
                    )

                    return {
                        "ok": True,
                        **result,
                    }

                except Exception as exc:
                    return {
                        "ok": False,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }

            if name in {
                "chooseSearchRoot",
                "chooseMediaFile",
                "chooseCreativeFile",
                "chooseCreativeWorkspace",
            }:
                return {
                    "selected": False,
                    "mobile_limited": True,
                    "reason": (
                        "Configure the workspace on Mary host "
                        "or with MARY_CREATIVE_WORKSPACE."
                    ),
                }

            if name in {
                "openCreativeWorkspaceFolder",
                "openDataFolder",
                "openWorkspaceFolder",
                "launchCreativeApp",
            }:
                return False

        raise KeyError(
            f"Unsupported mobile bridge method: {name}"
        )

    def close(
        self,
    ) -> None:
        with self._lock:
            self.application.close()


class MaryMobileRequestHandler(
    SimpleHTTPRequestHandler
):
    server_version = (
        "MaryMobile/1"
    )

    def __init__(
        self,
        *args: Any,
        directory: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *args,
            directory=directory,
            **kwargs,
        )

    @property
    def mary_server(
        self,
    ) -> "MaryMobileServer":
        return self.server  # type: ignore[return-value]

    def log_message(
        self,
        fmt: str,
        *args: Any,
    ) -> None:
        print(
            (
                f"[MaryMobile] "
                f"{self.address_string()} - "
                f"{fmt % args}"
            ),
            flush=True,
        )

    def _allowed_origin(
        self,
    ) -> str:
        origin = str(
            self.headers.get(
                "Origin",
                "",
            )
            or ""
        ).strip()

        if not origin:
            return ""

        defaults = {
            "capacitor://localhost",
            "http://localhost",
            "https://localhost",
            "null",
        }

        configured = {
            item.strip().rstrip("/")
            for item in os.getenv(
                "MARY_MOBILE_ALLOWED_ORIGINS",
                "",
            ).split(",")
            if item.strip()
        }

        if origin.rstrip("/") in (
            defaults
            | configured
        ):
            return origin

        return ""

    def do_OPTIONS(
        self,
    ) -> None:
        if not urlparse(
            self.path
        ).path.startswith(
            "/api/"
        ):
            self.send_error(
                HTTPStatus.NOT_FOUND
            )
            return

        origin = (
            self._allowed_origin()
        )

        if (
            self.headers.get(
                "Origin"
            )
            and not origin
        ):
            self.send_error(
                HTTPStatus.FORBIDDEN
            )
            return

        self.send_response(
            HTTPStatus.NO_CONTENT
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            (
                "Authorization, Content-Type, "
                "X-Mary-Audio-Filename"
            ),
        )

        self.send_header(
            "Access-Control-Max-Age",
            "600",
        )

        self.end_headers()

    def end_headers(
        self,
    ) -> None:
        origin = (
            self._allowed_origin()
        )

        if origin:
            self.send_header(
                "Access-Control-Allow-Origin",
                origin,
            )

            self.send_header(
                "Vary",
                "Origin",
            )

            self.send_header(
                "Access-Control-Expose-Headers",
                (
                    "X-Mary-Voice-Provider, "
                    "X-Mary-Voice-Model, "
                    "X-Mary-Voice-Status, "
                    "X-Mary-Voice-Cache"
                ),
            )

        if not urlparse(
            self.path
        ).path.startswith(
            "/api/"
        ):
            suffix = Path(
                urlparse(
                    self.path
                ).path
            ).suffix.lower()

            if (
                suffix
                in {
                    ".html",
                    ".js",
                    ".css",
                    ".webmanifest",
                }
                or self.path == "/"
            ):
                self.send_header(
                    "Cache-Control",
                    "no-cache",
                )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.send_header(
            "Referrer-Policy",
            "no-referrer",
        )

        self.send_header(
            "Permissions-Policy",
            (
                "camera=(), "
                "geolocation=(), "
                "microphone=(self)"
            ),
        )

        super().end_headers()

    def _authorized(
        self,
    ) -> bool:
        expected = (
            self.mary_server
            .auth
            .token
        )

        if not expected:
            return True

        supplied = self.headers.get(
            "Authorization",
            "",
        )

        return secrets.compare_digest(
            supplied,
            f"Bearer {expected}",
        )

    def _send_json(
        self,
        payload: Any,
        status: int = HTTPStatus.OK,
    ) -> None:
        raw = json.dumps(
            _json_safe(
                payload
            ),
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        self.send_response(
            int(
                status
            )
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(
                len(
                    raw
                )
            ),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.end_headers()

        self.wfile.write(
            raw
        )

    def _send_audio(
        self,
        audio: bytes,
        *,
        mime_type: str,
        metadata: dict[str, Any],
    ) -> None:
        self.send_response(
            HTTPStatus.OK
        )

        self.send_header(
            "Content-Type",
            str(
                mime_type
                or "application/octet-stream"
            ),
        )

        self.send_header(
            "Content-Length",
            str(
                len(
                    audio
                )
            ),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "X-Mary-Voice-Status",
            str(
                metadata.get(
                    "status"
                )
                or "success"
            ),
        )

        self.send_header(
            "X-Mary-Voice-Provider",
            str(
                metadata.get(
                    "provider"
                )
                or "unknown"
            )[:120],
        )

        self.send_header(
            "X-Mary-Voice-Model",
            str(
                metadata.get(
                    "model"
                )
                or ""
            )[:160],
        )

        self.send_header(
            "X-Mary-Voice-Cache",
            (
                "hit"
                if metadata.get(
                    "cached"
                )
                else "miss"
            ),
        )

        self.end_headers()

        self.wfile.write(
            audio
        )

    def _read_bytes(
        self,
        *,
        maximum: int,
    ) -> bytes:
        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

        except ValueError as exc:
            raise ValueError(
                "Invalid Content-Length."
            ) from exc

        if length <= 0:
            raise ValueError(
                "Request body is empty."
            )

        if length > maximum:
            raise OverflowError(
                "Request body is too large."
            )

        return (
            self.rfile
            .read(
                length
            )
        )

    def _read_json(
        self,
    ) -> dict[str, Any]:
        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

        except ValueError as exc:
            raise ValueError(
                "Invalid Content-Length."
            ) from exc

        if length <= 0:
            return {}

        if length > MAX_REQUEST_BYTES:
            raise OverflowError(
                "Request body is too large."
            )

        raw = (
            self.rfile
            .read(
                length
            )
        )

        try:
            value = json.loads(
                raw.decode(
                    "utf-8"
                )
            )

        except Exception as exc:
            raise ValueError(
                "Request body must be valid JSON."
            ) from exc

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                "Request JSON must be an object."
            )

        return value

    def _require_api_auth(
        self,
    ) -> bool:
        if self._authorized():
            return True

        self._send_json(
            {
                "ok": False,
                "error": "Unauthorized",
                "auth_required": True,
            },
            HTTPStatus.UNAUTHORIZED,
        )

        return False

    def do_GET(
        self,
    ) -> None:
        path = urlparse(
            self.path
        ).path

        if path == "/api/health":
            if not self._require_api_auth():
                return

            self._send_json(
                {
                    "ok": True,
                    "service": "MaryV2 Mobile",
                    "protocol": MOBILE_PROTOCOL_VERSION,
                    "auth": (
                        "token"
                        if self.mary_server.auth.enabled
                        else "loopback"
                    ),
                    "status": (
                        self.mary_server
                        .runtime
                        .status()
                    ),
                }
            )

            return

        if path == "/api/state":
            if not self._require_api_auth():
                return

            self._send_json(
                self.mary_server
                .runtime
                .dashboard_state()
            )

            return

        if path == "/api/trace":
            if not self._require_api_auth():
                return

            self._send_json(
                self.mary_server
                .runtime
                .last_turn_trace()
            )

            return

        if path == "/api/experience":
            if not self._require_api_auth():
                return

            dashboard = (
                self.mary_server
                .runtime
                .dashboard_state()
            )
            trace = (
                self.mary_server
                .runtime
                .last_turn_trace()
            )

            self._send_json(
                {
                    "ok": True,
                    **build_experience_snapshot(
                        dashboard,
                        trace,
                    ),
                }
            )

            return

        if path == "/api/voice/status":
            if not self._require_api_auth():
                return

            self._send_json(
                {
                    "ok": True,
                    **(
                        self.mary_server
                        .runtime
                        .voice_status()
                    ),
                }
            )

            return

        if path == "/api/lifecycle/status":
            if not self._require_api_auth():
                return

            self._send_json(
                {
                    "ok": True,
                    "lifecycle": (
                        self.mary_server
                        .runtime
                        .lifecycle_status()
                    ),
                }
            )

            return

        if path.startswith(
            "/api/"
        ):
            self._send_json(
                {
                    "ok": False,
                    "error": "Unknown API route.",
                },
                HTTPStatus.NOT_FOUND,
            )

            return

        # SPA fallback: unknown extensionless routes reopen the Mary UI.
        parsed = Path(
            path
        )

        if (
            path != "/"
            and not parsed.suffix
        ):
            self.path = (
                "/index.html"
            )

        return super().do_GET()

    def do_POST(
        self,
    ) -> None:
        path = urlparse(
            self.path
        ).path

        if not path.startswith(
            "/api/"
        ):
            self._send_json(
                {
                    "ok": False,
                    "error": (
                        "POST is only supported for API routes."
                    ),
                },
                HTTPStatus.NOT_FOUND,
            )

            return

        if not self._require_api_auth():
            return

        try:
            if path == "/api/stt":
                raw = self._read_bytes(
                    maximum=MAX_AUDIO_REQUEST_BYTES
                )

                payload = (
                    self.mary_server
                    .runtime
                    .transcribe_audio(
                        raw,
                        filename=self.headers.get(
                            "X-Mary-Audio-Filename"
                        ),
                        content_type=self.headers.get(
                            "Content-Type"
                        ),
                    )
                )

                self._send_json(
                    {
                        "ok": True,
                        **payload,
                    }
                )

                return

            body = (
                self._read_json()
            )

            if path == "/api/lifecycle/register":
                payload = self.mary_server.runtime.surface_register(
                    surface_id=body.get("surface_id"),
                    visible=bool(body.get("visible", True)),
                    foreground=bool(body.get("foreground", True)),
                    lease_seconds=body.get("lease_seconds", 90),
                )
                self._send_json({"ok": True, "lifecycle": payload})
                return

            if path == "/api/lifecycle/renew":
                visible = body.get("visible")
                foreground = body.get("foreground")
                if visible is not None and not isinstance(visible, bool):
                    raise ValueError("visible must be a boolean.")
                if foreground is not None and not isinstance(foreground, bool):
                    raise ValueError("foreground must be a boolean.")
                payload = self.mary_server.runtime.surface_renew(
                    surface_id=body.get("surface_id"),
                    visible=visible,
                    foreground=foreground,
                    activity=str(body.get("activity") or "heartbeat"),
                )
                self._send_json({"ok": True, "lifecycle": payload})
                return

            if path == "/api/lifecycle/disconnect":
                payload = self.mary_server.runtime.surface_disconnect(
                    surface_id=body.get("surface_id"),
                )
                self._send_json({"ok": True, "lifecycle": payload})
                return

            if path == "/api/lifecycle/wake":
                payload = self.mary_server.runtime.surface_wake(
                    surface_id=body.get("surface_id"),
                )
                self._send_json({"ok": True, "lifecycle": payload})
                return

            if path == "/api/chat":
                payload = (
                    self.mary_server
                    .runtime
                    .chat(
                        str(
                            body.get(
                                "text"
                            )
                            or ""
                        ),
                        conversation_id=(
                            str(
                                body.get(
                                    "conversation_id"
                                )
                                or ""
                            ).strip()
                            or None
                        ),
                        voice_input=bool(
                            body.get(
                                "voice_input",
                                False,
                            )
                        ),
                    )
                )

                self._send_json(
                    {
                        "ok": True,
                        **payload,
                    }
                )

                return

            if path == "/api/tts":
                delivery_plan = (
                    body.get(
                        "delivery_plan"
                    )
                    or {}
                )

                if not isinstance(
                    delivery_plan,
                    dict,
                ):
                    raise ValueError(
                        "delivery_plan must be a JSON object."
                    )

                speech = (
                    self.mary_server
                    .runtime
                    .synthesize_speech(
                        str(
                            body.get(
                                "text"
                            )
                            or ""
                        ),
                        user_text=(
                            str(
                                body.get(
                                    "user_text"
                                )
                                or ""
                            )
                            or None
                        ),
                        delivery_plan=delivery_plan,
                    )
                )

                if speech.successful:
                    self._send_audio(
                        speech.audio,
                        mime_type=speech.mime_type,
                        metadata={
                            **speech.metadata,
                            "cached": speech.cached,
                        },
                    )

                else:
                    self._send_json(
                        {
                            "ok": False,
                            "fallback": "device",
                            **speech.metadata,
                        },
                        HTTPStatus.SERVICE_UNAVAILABLE,
                    )

                return

            if path == "/api/bridge":
                method = str(
                    body.get(
                        "method"
                    )
                    or ""
                )

                args = (
                    body.get(
                        "args"
                    )
                    or []
                )

                if not isinstance(
                    args,
                    list,
                ):
                    raise ValueError(
                        "Bridge args must be a JSON array."
                    )

                payload = (
                    self.mary_server
                    .runtime
                    .bridge_call(
                        method,
                        args,
                    )
                )

                self._send_json(
                    {
                        "ok": True,
                        "result": payload,
                    }
                )

                return

            self._send_json(
                {
                    "ok": False,
                    "error": "Unknown API route.",
                },
                HTTPStatus.NOT_FOUND,
            )

        except OverflowError as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                },
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        except KeyError as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                },
                HTTPStatus.NOT_FOUND,
            )

        except (
            ValueError,
            TypeError,
        ) as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                },
                HTTPStatus.BAD_REQUEST,
            )

        except RuntimeError as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                },
                HTTPStatus.CONFLICT,
            )

        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


class MaryMobileServer(
    ThreadingHTTPServer
):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[
            str,
            int,
        ],
        *,
        runtime: MaryMobileRuntime,
        static_root: Path,
        auth: MobileAuth,
    ) -> None:
        self.runtime = (
            runtime
        )

        self.static_root = (
            Path(
                static_root
            )
            .resolve()
        )

        self.auth = (
            auth
        )

        handler = partial(
            MaryMobileRequestHandler,
            directory=str(
                self.static_root
            ),
        )

        super().__init__(
            address,
            handler,
        )

    def server_close(
        self,
    ) -> None:
        try:
            self.runtime.close()

        finally:
            super().server_close()


def _project_root(
) -> Path:
    return (
        Path(
            __file__
        )
        .resolve()
        .parents[2]
    )


def _static_root(
    root: Path,
) -> Path:
    configured = os.getenv(
        "MARY_MOBILE_STATIC_ROOT",
        "",
    ).strip()

    if configured:
        return (
            Path(
                configured
            )
            .expanduser()
            .resolve()
        )

    # Mobile is a first-class surface, not a responsive fallback for Desktop.
    # Prefer the dedicated phone UI even when desktop/dist happens to exist on
    # the same development host (common on Replit/GitHub/PC working copies).
    standalone = (
        root
        / "mobile_web"
    )

    if (
        standalone
        / "index.html"
    ).exists():
        return standalone

    # An explicit escape hatch remains for development/recovery builds where
    # only the compiled desktop frontend is available.
    built = (
        root
        / "desktop"
        / "dist"
    )

    if (
        built
        / "index.html"
    ).exists():
        return built

    return (
        root
        / "desktop"
    )


def run_mobile_server(
    *,
    host: str | None = None,
    port: int | None = None,
    application: MaryApplication | None = None,
) -> None:
    root = (
        _project_root()
    )

    resolved_host = (
        host
        or _default_host()
    )

    resolved_port = int(
        port
        or _default_port()
    )

    core_url = os.getenv(
        "MARY_CORE_URL",
        "",
    ).strip()

    if core_url:
        if application is not None:
            raise RuntimeError(
                "application= cannot be combined with "
                "MARY_CORE_URL remote-client mode."
            )

        core_token = os.getenv(
            "MARY_CORE_TOKEN",
            "",
        ).strip()

        if not core_token:
            raise RuntimeError(
                "MARY_CORE_TOKEN is required when "
                "MARY_CORE_URL enables remote-client mode."
            )

        runtime = MaryRemoteMobileRuntime(
            core_url,
            token=core_token,
            device_id=(
                os.getenv(
                    "MARY_DEVICE_ID",
                    "replit-mobile",
                ).strip()
                or "replit-mobile"
            ),
        )

        auth_data_root = (
            runtime.data_root
        )

    else:
        runtime = (
            MaryMobileRuntime(
                application
            )
        )

        auth_data_root = Path(
            runtime.application
            .mary
            .config
            .paths
            .data
        )

    static_root = (
        _static_root(
            root
        )
    )

    auth = _resolve_auth(
        host=resolved_host,
        data_root=auth_data_root,
    )

    if not (
        static_root
        / "index.html"
    ).exists():
        runtime.close()

        raise RuntimeError(
            f"Mobile UI not found at {static_root}. "
            "Run `cd desktop && npm ci && npm run build` first."
        )

    server = MaryMobileServer(
        (
            resolved_host,
            resolved_port,
        ),
        runtime=runtime,
        static_root=static_root,
        auth=auth,
    )

    print(
        "=" * 68,
        flush=True,
    )

    print(
        "MARYV2 MOBILE COMPANION",
        flush=True,
    )

    print(
        "=" * 68,
        flush=True,
    )

    print(
        f"Host: {resolved_host}",
        flush=True,
    )

    print(
        f"Port: {resolved_port}",
        flush=True,
    )

    print(
        f"UI:   {static_root}",
        flush=True,
    )

    if auth.enabled:
        print(
            "Mobile API protection: bearer token",
            flush=True,
        )

        if auth.source == "generated":
            print(
                "",
                flush=True,
            )

            print(
                "FIRST-RUN MOBILE ACCESS TOKEN",
                flush=True,
            )

            print(
                auth.token,
                flush=True,
            )

            print(
                (
                    "Enter this once in the Mary mobile app. "
                    "It is saved on this device."
                ),
                flush=True,
            )

        elif auth.source == "persisted":
            print(
                f"Token loaded from: {auth.token_path}",
                flush=True,
            )

        else:
            print(
                "Token loaded from MARY_MOBILE_TOKEN.",
                flush=True,
            )

    else:
        print(
            (
                "Mobile API protection: loopback-only "
                "(no token required)"
            ),
            flush=True,
        )

    print(
        "",
        flush=True,
    )

    if core_url:
        device_id = (
            os.getenv(
                "MARY_DEVICE_ID",
                "replit-mobile",
            ).strip()
            or "replit-mobile"
        )

        print(
            "Mode: remote-core client",
            flush=True,
        )

        print(
            "Mobile authority: remote_mary_core",
            flush=True,
        )

        print(
            f"Core URL: {core_url.rstrip('/')}",
            flush=True,
        )

        print(
            f"Device ID: {device_id}",
            flush=True,
        )

        print(
            "Canonical state authority: Mary Core",
            flush=True,
        )

        print(
            "This mobile surface does not create a second Mary.",
            flush=True,
        )

    else:
        print(
            "Mode: local MaryApplication",
            flush=True,
        )

        print(
            "Mobile authority: local development runtime",
            flush=True,
        )

        print(
            (
                "Canonical state authority: "
                "local MaryApplication"
            ),
            flush=True,
        )

    print(
        "=" * 68,
        flush=True,
    )

    try:
        server.serve_forever(
            poll_interval=0.25
        )

    except KeyboardInterrupt:
        pass

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run_mobile_server()