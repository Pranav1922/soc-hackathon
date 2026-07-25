"""Response Formatter — assemble the final structured response (D12).

Invoked **after** the executor finishes (never a planner-selected step, D3). Merges
the query, understanding, plan, skipped tools, results, charts, and trace into the
single :class:`app.schemas.APIResponse` object the UI/judge inspects.

Its identity in the tool inventory is :attr:`ToolName.RESPONSE_FORMATTER` (D5), but
because it is post-execution it does not implement the :class:`Tool` run-loop
contract; it exposes a dedicated :meth:`format` method instead.
"""

from __future__ import annotations

import logging

from app.enums import ToolName
from app.schemas import APIResponse, Context, ExecutionPlan

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Builds the frozen response contract from the executed context and plan."""

    name: ToolName = ToolName.RESPONSE_FORMATTER

    def format(self, context: Context, plan: ExecutionPlan) -> APIResponse:
        """Assemble the final :class:`APIResponse` (D12) — pure field mapping.

        Reads the executed state and maps it directly onto the frozen response
        shape. No computation, no scoring/explanation, and no mutation of
        ``context`` or ``plan``. An empty ``results`` list is a valid response
        (D11); the reason is already carried by ``trace``.

        Args:
            context: The context after all planned steps have run (query,
                understanding, flags, charts, trace).
            plan: The plan that was executed (for ``plan``/``skipped``).

        Returns:
            The single structured response object (D12 shape).
        """
        response = APIResponse(
            query=context.query,
            understanding=context.understanding,
            plan=plan.steps,
            skipped=plan.skipped,
            results=context.flags,
            charts=context.charts,
            trace=context.trace,
        )
        logger.info(
            "Response assembled: %d step(s), %d skipped, %d result(s), "
            "%d chart(s), %d trace entr(y/ies)",
            len(response.plan),
            len(response.skipped),
            len(response.results),
            len(response.charts),
            len(response.trace),
        )
        return response
