"""The agent "hands": one tool per file.

Every tool implements :class:`app.interfaces.Tool` with the uniform signature
``run(context, params) -> (context, ToolResult, TraceEntry)`` and tolerates empty
input. Tools never decide the plan; the deterministic planner selects which ones run.
"""
