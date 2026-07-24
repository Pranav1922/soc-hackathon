"""Tool-set wiring — the registry the executor runs against (D4).

Single place that maps every planner-selectable :class:`ToolName` to its concrete
:class:`Tool` instance. The executor iterates a plan *by name* and looks tools up
here, so it never needs to change when a tool is added.

``ToolName`` itself is defined once in :mod:`app.enums` and re-exported here so this
module stays the tool hub (per ``docs/FOLDER_STRUCTURE.md``) without creating a
circular import against ``schemas`` (which also needs ``ToolName``).

Note: :class:`ToolName.RESPONSE_FORMATTER` is intentionally **not** in the run
registry — it is invoked post-execution by :class:`app.response.ResponseFormatter`,
never as a planned step (D3, D5).
"""

from __future__ import annotations

from app.enums import ToolName  # re-exported; see module docstring
from app.interfaces import Tool
from app.tools.aml_patterns import AMLPatternDetector
from app.tools.anomaly import AnomalyDetector
from app.tools.data_loader import DataLoader
from app.tools.eda import EDA
from app.tools.explainer import Explainer
from app.tools.feature_engineering import FeatureEngineering
from app.tools.filter_tool import Filter
from app.tools.recommender import Recommender
from app.tools.risk_classifier import RiskClassifier
from app.tools.visualizer import Visualizer

__all__ = ["TOOLS", "ToolName", "get_tool"]


def _build_registry() -> dict[ToolName, Tool]:
    """Instantiate every runnable tool once and index it by its ``ToolName``.

    Instantiation is side-effect-free (tools do their work in ``run``), so building
    this at import time is safe.
    """

    tools: list[Tool] = [
        DataLoader(),
        Filter(),
        EDA(),
        FeatureEngineering(),
        AMLPatternDetector(),
        AnomalyDetector(),
        RiskClassifier(),
        Explainer(),
        Recommender(),
        Visualizer(),
    ]
    registry = {tool.name: tool for tool in tools}
    # Fail fast if a tool's declared name doesn't match / duplicates another.
    assert len(registry) == len(tools), "Duplicate ToolName in the tool registry"
    return registry


#: The runnable tool registry (10 planner-selectable tools; excludes ResponseFormatter).
TOOLS: dict[ToolName, Tool] = _build_registry()


def get_tool(name: ToolName) -> Tool:
    """Look up a runnable tool by name.

    Raises:
        KeyError: if ``name`` is not a runnable tool (e.g. ``RESPONSE_FORMATTER``).
    """

    return TOOLS[name]
