"""
MaryV2 - Tools Package

Public interface for Mary's controlled tool system.

This package provides capabilities for:

    - tool registration
    - controlled web access
    - controlled filesystem access
    - source-code inspection and modification

IMPORTANT
---------

Importing this package does NOT:

    - create a ToolRegistry
    - register tools
    - grant permissions
    - access the internet
    - access the filesystem
    - execute code

Capabilities must be explicitly constructed and registered by the
application.

External access and state-changing operations remain subject to
ToolRegistry permission controls.
"""

from .registry import (
    ToolRegistry,
    ToolResult,
    ToolDefinition,
    PermissionLevel,
)

from .web import (
    WebClient,
    WebConfig,
    WebPage,
    SearchResult,
    TavilySearchProvider,
    BraveSearchProvider,
    create_search_provider,
    create_web_client,
    register_web_tools,
)

from .filesystem import (
    FilesystemClient,
    FilesystemConfig,
    FileInfo,
    create_filesystem_client,
    register_filesystem_tools,
)

from .code import (
    CodeClient,
    CodeAnalysis,
    CodeChange,
    create_code_client,
    register_code_tools,
)

from .manager import ToolManager


__all__ = [
    # Registry
    "ToolRegistry",
    "ToolResult",
    "ToolDefinition",
    "PermissionLevel",

    # Web
    "WebClient",
    "WebConfig",
    "WebPage",
    "SearchResult",
    "TavilySearchProvider",
    "BraveSearchProvider",
    "create_search_provider",
    "create_web_client",
    "register_web_tools",

    # Filesystem
    "FilesystemClient",
    "FilesystemConfig",
    "FileInfo",
    "create_filesystem_client",
    "register_filesystem_tools",

    # Code
    "CodeClient",
    "CodeAnalysis",
    "CodeChange",
    "create_code_client",
    "register_code_tools",
]