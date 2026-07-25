"""ML Pipeline orchestrator — the reusable in-process agent loop (D1, D13).

Wires the four completed Developer-A components into one call:

    query → QueryUnderstanding → Planner → Executor → ResponseFormatter → APIResponse

It only *coordinates* those modules — it performs no business logic, no planning,
no tool execution, and no scoring. The dynamic behaviour (which tools run for a
given query) lives entirely inside the Planner and Executor; this class just threads
their outputs. It is deliberately framework-agnostic (D13): the FastAPI layer and the
Streamlit UI both call the same :class:`Pipeline` in-process.

Startup (once): the dataset is loaded so the query-understanding step can be grounded
with the real schema (D10). If the dataset is missing/unreadable, construction still
succeeds and the pipeline runs with an empty schema (degraded, never failing).
"""

from __future__ import annotations

import logging

from app.agent.executor import Executor
from app.agent.planner import DeterministicPlanner
from app.agent.understanding import LLMQueryUnderstanding
from app.interfaces import Planner, QueryUnderstanding
from app.response import ResponseFormatter
from app.schemas import APIResponse, Context
from app.tools.data_loader import DataLoader

logger = logging.getLogger(__name__)


class Pipeline:
    """Coordinates the completed agent modules to answer a query end-to-end.

    Components are constructed once and reused across queries. Dependencies are
    injectable for testing; defaults are the real completed implementations.
    """

    def __init__(
        self,
        understanding: QueryUnderstanding | None = None,
        planner: Planner | None = None,
        executor: Executor | None = None,
        formatter: ResponseFormatter | None = None,
    ) -> None:
        self._understanding: QueryUnderstanding = understanding or LLMQueryUnderstanding()
        self._planner: Planner = planner or DeterministicPlanner()
        self._executor: Executor = executor or Executor()
        self._formatter: ResponseFormatter = formatter or ResponseFormatter()
        self._schema_map: dict[str, str] = self._load_schema()

    # ── public API ────────────────────────────────────────────────────────────

    def analyze(self, query: str) -> APIResponse:
        """Run the full agent loop for a query and return one :class:`APIResponse`.

        Flow: understand → plan → execute → format. Each stage delegates to its
        module; the executor already isolates individual tool failures, so this
        method returns a valid response even when some tools are unimplemented or
        the dataset is missing.
        """
        understanding = self._understanding.understand(query, self._schema_map)
        plan = self._planner.build_plan(understanding)
        context = Context(query=query, understanding=understanding)
        context = self._executor.run_plan(context, plan)
        response = self._formatter.format(context, plan)
        logger.info(
            "Pipeline analysed query: intent=%s, %d step(s), %d result(s)",
            understanding.intent.value,
            len(response.plan),
            len(response.results),
        )
        return response

    @property
    def schema_map(self) -> dict[str, str]:
        """The dataset schema cached at startup (empty if the load failed)."""
        return self._schema_map

    # ── startup ───────────────────────────────────────────────────────────────

    def _load_schema(self) -> dict[str, str]:
        """Load the dataset once to cache its schema for query understanding (D10).

        Never raises: on any failure (missing file, bad format) it logs and returns
        an empty schema so construction succeeds and queries still run.
        """
        boot = Context(query="")
        _, _, trace = DataLoader().run(boot, {})
        if boot.schema_map:
            logger.info("Pipeline: loaded dataset schema (%d columns)", len(boot.schema_map))
        else:
            logger.warning(
                "Pipeline: dataset schema unavailable (DataLoader status=%s); "
                "query understanding will run without schema grounding",
                trace.status.value,
            )
        return boot.schema_map
