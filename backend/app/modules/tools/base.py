"""Tool contract: context, risk, and base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.types import ToolSpec


class RiskLevel(StrEnum):
    """Tool risk classification."""

    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    CONFIRMATION_REQUIRED = "confirmation_required"


class Mode(StrEnum):
    """Assistant network mode."""

    INTERNAL_ONLY = "internal_only"
    EXTERNAL_ALLOWED = "external_allowed"


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Authenticated run context — never taken from model args."""

    user_id: UUID
    conversation_id: UUID
    run_id: UUID
    mode: Mode
    session: AsyncSession


class BaseTool(ABC):
    """One tool wrapping a domain service method."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    read_only: bool = True
    touches_external: bool = False
    allowed_in_internal_only: bool = True
    timeout_ms: int = 10_000
    confirmation_schema: type[BaseModel] | None = None

    def to_spec(self) -> ToolSpec:
        """JSON-schema ToolSpec for the LLM."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=_parameters_schema(self.input_model),
        )

    @abstractmethod
    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        """Raise ToolAuthzError if the user may not run this call."""

    @abstractmethod
    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        """Call the domain service; return output_model instance."""


def _parameters_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    return {
        "type": "object",
        "properties": raw.get("properties", {}),
        "required": raw.get("required", []),
    }
