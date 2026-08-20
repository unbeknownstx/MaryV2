"""Convenience launcher for MaryV2 terminal mode.

Both of these now enter the same canonical runtime::

    python run_mary.py
    python -m scripts.run_mary

The module contains no separate Mary implementation; it delegates directly to
``scripts.run_mary.main`` so there is still one application path.
"""

from __future__ import annotations

from scripts.run_mary import main


if __name__ == "__main__":
    main()
