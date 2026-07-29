"""propose_choices — clarify UI chips (not a HITL gate)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class ProposeChoicesInput(BaseModel):
    """Ambiguous intent: offer short labels the user can tap."""

    prompt: str = Field(
        min_length=1,
        max_length=240,
        description="Short question shown above the choice chips",
    )
    options: list[str] = Field(
        min_length=2,
        max_length=5,
        description="2-5 short labels; picking one sends that text as the next user message",
    )


class ProposeChoicesOutput(BaseModel):
    """Options for the client choice_request event."""

    prompt: str
    options: list[str]
    message: str


class ProposeChoicesTool(BaseTool):
    """Surface clarify choices as chat chips (does not execute side effects)."""

    name = "propose_choices"
    description = (
        "When the user's intent is ambiguous or several library/discovery matches "
        "exist, call this with a short prompt and 2-5 option labels. The UI shows "
        "chips; the user's pick is a normal follow-up message. Do not use this for "
        "scrape/import confirmation — that uses the confirmation form."
    )
    input_model = ProposeChoicesInput
    output_model = ProposeChoicesOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 2_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        pass

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ProposeChoicesInput.model_validate(inp.model_dump())
        cleaned = [opt.strip() for opt in data.options if opt.strip()][:5]
        return ProposeChoicesOutput(
            prompt=data.prompt.strip(),
            options=cleaned,
            message=data.prompt.strip(),
        )
