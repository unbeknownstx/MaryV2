"""Optional durable database projections for MaryV2.

Database projections are deliberately downstream of Mary's canonical state.
They may store/query evidence and retrieval candidates, but they never become
identity, relationship, memory, agency, or permission authority.
"""

from .postgres_projection import (
    PostgresProjection,
    PostgresProjectionConfig,
    ProjectionRecord,
    memory_projection_records,
)

__all__ = [
    "PostgresProjection",
    "PostgresProjectionConfig",
    "ProjectionRecord",
    "memory_projection_records",
]
