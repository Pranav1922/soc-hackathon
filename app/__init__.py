"""AI-Powered Suspicious Activity Detection — modular monolith.

The whole application lives under this single package (one deployable, no
microservices). Public building blocks:

* :mod:`app.enums`      — shared enumerations (single source of truth).
* :mod:`app.schemas`    — shared Pydantic models (the frozen contracts).
* :mod:`app.interfaces` — abstract base classes implemented by the tools/agent.
* :mod:`app.config`     — frozen constants + env-driven settings.

See ``docs/FINAL_ARCHITECTURE_DECISIONS.md`` for the frozen architecture.
"""

__version__ = "0.1.0"
