"""Tool registry."""

from __future__ import annotations

from app.modules.llm.types import ToolSpec
from app.modules.tools.base import BaseTool, Mode
from app.modules.tools.exceptions import ToolNotFoundError


class ToolRegistry:
    """Name → tool lookup; mode-filtered specs for the LLM."""

    def __init__(self, tools: list[BaseTool]) -> None:
        self._by_name = {t.name: t for t in tools}
        if len(self._by_name) != len(tools):
            raise ValueError("duplicate tool names in registry")

    def resolve(self, name: str) -> BaseTool:
        """Return tool or raise ToolNotFoundError."""
        tool = self._by_name.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def list_specs(self, mode: Mode) -> list[ToolSpec]:
        """Tool schemas visible to the model in this mode."""
        return [t.to_spec() for t in self._by_name.values() if _visible(t, mode)]


def _visible(tool: BaseTool, mode: Mode) -> bool:
    if mode != Mode.INTERNAL_ONLY:
        return True
    return not tool.touches_external and tool.allowed_in_internal_only
