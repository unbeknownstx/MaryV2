"""Small obs-websocket 5.x protocol helpers for a Mary capability node."""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ObsHello:
    rpc_version: int
    challenge: str = ""
    salt: str = ""

    @property
    def authentication_required(self) -> bool:
        return bool(self.challenge and self.salt)


def parse_hello(message: Mapping[str, Any]) -> ObsHello:
    if int(message.get("op", -1)) != 0:
        raise ValueError("OBS hello must use opcode 0")
    data = message.get("d")
    if not isinstance(data, Mapping):
        raise ValueError("OBS hello missing message data")
    auth = data.get("authentication")
    auth = auth if isinstance(auth, Mapping) else {}
    return ObsHello(
        rpc_version=max(1, int(data.get("rpcVersion", 1) or 1)),
        challenge=str(auth.get("challenge") or ""),
        salt=str(auth.get("salt") or ""),
    )


def authentication_string(password: str, hello: ObsHello) -> str:
    if not hello.authentication_required:
        return ""
    secret = base64.b64encode(
        hashlib.sha256((str(password) + hello.salt).encode("utf-8")).digest()
    ).decode("ascii")
    return base64.b64encode(
        hashlib.sha256((secret + hello.challenge).encode("utf-8")).digest()
    ).decode("ascii")


def identify_message(hello: ObsHello, *, password: str = "", event_subscriptions: int = 1) -> dict[str, Any]:
    data: dict[str, Any] = {
        "rpcVersion": hello.rpc_version,
        "eventSubscriptions": max(0, int(event_subscriptions)),
    }
    if hello.authentication_required:
        data["authentication"] = authentication_string(password, hello)
    return {"op": 1, "d": data}


def normalize_obs_event(message: Mapping[str, Any]) -> dict[str, Any] | None:
    if int(message.get("op", -1)) != 5:
        return None
    data = message.get("d")
    if not isinstance(data, Mapping):
        return None
    event_type = str(data.get("eventType") or "")[:120]
    event_data = data.get("eventData")
    if not event_type:
        return None
    safe: dict[str, Any] = {}
    if isinstance(event_data, Mapping):
        for key, value in list(event_data.items())[:24]:
            clean = str(key)[:80]
            lowered = clean.casefold()
            if any(secret in lowered for secret in ("password", "token", "secret", "auth")):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[clean] = value if not isinstance(value, str) else value[:300]
    return {
        "kind": f"obs.{event_type}",
        "source": "obs-websocket",
        "summary": event_type,
        "metadata": safe,
        "authority": "environment_context_only",
    }
