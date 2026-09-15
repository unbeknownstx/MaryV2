"""Provider/model substitution detection for MaryV2 13.64."""
from __future__ import annotations
from dataclasses import dataclass

VERSION = "13.64"

@dataclass(frozen=True)
class RouteIdentity:
    requested_provider: str
    requested_model: str
    served_provider: str | None = None
    served_model: str | None = None

    def substitution(self) -> str:
        if self.served_provider is None and self.served_model is None:
            return "unreported"
        provider_changed = self.served_provider is not None and self.served_provider != self.requested_provider
        model_changed = self.served_model is not None and self.served_model != self.requested_model
        if provider_changed or model_changed:
            return "substituted"
        return "matched"

def enforce_identity(identity: RouteIdentity, *, allow_provider_substitution: bool = False, allow_model_substitution: bool = False) -> None:
    if identity.served_provider is not None and identity.served_provider != identity.requested_provider and not allow_provider_substitution:
        raise RuntimeError("provider substitution rejected")
    if identity.served_model is not None and identity.served_model != identity.requested_model and not allow_model_substitution:
        raise RuntimeError("model substitution rejected")
