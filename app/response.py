"""Response Formatter — assemble the final structured response (D12).

Invoked **after** the executor finishes (never a planner-selected step, D3). Merges
the query, understanding, plan, skipped tools, results, charts, and trace into the
single :class:`app.schemas.APIResponse` object the UI/judge inspects.

Its identity in the tool inventory is :attr:`ToolName.RESPONSE_FORMATTER` (D5), but
because it is post-execution it does not implement the :class:`Tool` run-loop
contract; it exposes a dedicated :meth:`format` method instead.
"""

from __future__ import annotations

from app.enums import ToolName
from app.schemas import APIResponse, Context, ExecutionPlan


class ResponseFormatter:
    """Builds the frozen response contract from the executed context and plan."""

    name: ToolName = ToolName.RESPONSE_FORMATTER

    def format(self, context: Context, plan: ExecutionPlan) -> APIResponse:
        """Assemble the final :class:`APIResponse`.

        Args:
            context: The context after all planned steps have run (flags, charts,
                trace, understanding).
            plan: The plan that was executed (for ``plan``/``skipped``).

        Returns:
            The single structured response object (D12 shape).
        """
        # TODO(Phase 1): construct APIResponse from context + plan (no computation,
        # pure assembly). Include the empty-result explanation path (D11).
        raise NotImplementedError("ResponseFormatter.format — implemented in Phase 1")
