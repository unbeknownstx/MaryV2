"""Desktop authority resolver for standalone vs canonical remote Mary Core.

Dependency-light on purpose so the authority decision can be tested without Qt.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from mary.desktop.remote_application import RemoteMaryApplicationView
from mary.runtime.application import MaryApplication, create_application
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment


def resolve_desktop_application(
    application: MaryApplication | None = None,
    *,
    project_root: Path | None = None,
) -> tuple[MaryApplication | RemoteMaryApplicationView, Path]:
    """Resolve Desktop authority without ever creating two Mary runtimes."""

    load_dotenv()
    core_url = os.getenv("MARY_CORE_URL", "").strip()

    if core_url:
        if application is not None:
            raise RuntimeError(
                "MARY_CORE_URL selects remote Desktop client mode; do not supply "
                "a local MaryApplication because that would create two authorities."
            )

        gateway = gateway_from_environment(
            application=None,
            device_id=(
                os.getenv("MARY_NODE_ID", "").strip()
                or os.getenv("COMPUTERNAME", "").strip()
                or os.getenv("HOSTNAME", "").strip()
                or "desktop"
            ),
            surface="desktop",
        )

        if not isinstance(gateway, RemoteMaryGateway):
            raise RuntimeError("Desktop remote mode did not resolve a remote Mary gateway.")

        root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        return (
            RemoteMaryApplicationView(
                gateway,
                project_root=root,
                conversation_id=os.getenv("MARY_CONVERSATION_ID", "creator-primary"),
            ),
            root,
        )

    mary_app = application or create_application(name="mary-desktop")
    return mary_app, Path(mary_app.mary.config.paths.root)
