"""Entry point for ``python3 -m quoteshot``.

Equivalent to the installed ``quoteshot`` command: both call
:func:`quoteshot.cli.main`. Run ``python3 -m quoteshot --help`` for
the command list and a worked workflow.
"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
