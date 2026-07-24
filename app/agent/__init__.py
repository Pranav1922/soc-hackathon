"""The agent "brain": coordination logic.

Contains Query Understanding (the single LLM call), the *deterministic* Planner,
the Executor, and the tool-set wiring. This package decides *what* to run and in
*what order*; it never computes numbers itself (that is the tools' job).
"""
