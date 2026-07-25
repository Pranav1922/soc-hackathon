"""Response Formatter — assemble the final structured response (D12).

Invoked **after** the executor finishes (never a planner-selected step, D3). Merges
the query, understanding, plan, skipped tools, results, charts, and trace into the
single :class:`app.schemas.APIResponse` object the UI/judge inspects.

Its identity in the tool inventory is :attr:`ToolName.RESPONSE_FORMATTER` (D5), but
because it is post-execution it does not implement the :class:`Tool` run-loop
contract; it exposes a dedicated :meth:`format` method instead.

**On D11's "no flags found + why" requirement:** the frozen :class:`APIResponse`
shape (D12) has exactly seven fields and none of them is free text — adding one
would mean modifying a frozen contract, which this module must not do. The "why"
is already reconstructable from the fields that *do* exist: ``trace`` carries each
step's ``rows_in``/``rows_out`` (e.g. Filter: 1000 in, 0 out), and ``understanding``
carries the filters that produced that narrowing (e.g. ``last_days: 30``). This
formatter's job — per its own TODO, "no computation, pure assembly" — is to pass
those through completely and honestly, never to synthesize new prose. The UI is
what renders "0 transactions after the 30-day filter" from ``trace`` +
``understanding``, not this module.
"""

from __future__ import annotations

from app.enums import ToolName
from app.schemas import APIResponse, Context, ExecutionPlan


class ResponseFormatter:
    """Builds the frozen response contract from the executed context and plan."""

    name: ToolName = ToolName.RESPONSE_FORMATTER

    def format(self, context: Context, plan: ExecutionPlan) -> APIResponse:
        """Assemble the final :class:`APIResponse`.

        Pure assembly — no computation, no filtering, no re-deriving values.
        Every field is read directly from ``context``/``plan``; an empty
        ``results``/``charts``/``trace`` list is passed through as-is (D11: a
        first-class, valid state, not an error).

        Args:
            context: The context after all planned steps have run (flags, charts,
                trace, understanding).
            plan: The plan that was executed (for ``plan``/``skipped``).

        Returns:
            The single structured response object (D12 shape).
        """
        return APIResponse(
            query=context.query,
            understanding=context.understanding,
            plan=plan.steps,
            skipped=plan.skipped,
            results=context.flags,
            charts=context.charts,
            trace=context.trace,
        )
