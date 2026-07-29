"""update_ui_settings — validated reversible client preferences."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class UpdateUiSettingsInput(BaseModel):
    """Allowlisted UI and playback settings; omitted values remain unchanged."""

    theme: Literal["light", "dark", "system"] | None = None
    font_size: float | None = Field(default=None, ge=1.0, le=1.8)
    max_playback_rate: float | None = Field(default=None, ge=1.0, le=4.0)
    playback_rate: float | None = Field(default=None, ge=0.5, le=4.0)
    playback_engine: Literal["browser", "server"] | None = None
    tts_provider: Literal["edge", "sapi"] | None = None
    voice: str | None = Field(default=None, max_length=200)
    highlighting: Literal["auto", "word", "paragraph"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> UpdateUiSettingsInput:
        if not self.model_fields_set:
            raise ValueError("At least one setting must be provided")
        return self


class UpdateUiSettingsOutput(UpdateUiSettingsInput):
    """Validated settings patch for the client."""

    message: str


class UpdateUiSettingsTool(BaseTool):
    """Return an allowlisted settings patch for client-side application."""

    name = "update_ui_settings"
    description = (
        "Change reversible website preferences: theme, reader font size, maximum playback "
        "rate, current playback rate, browser/server playback engine, Edge/SAPI provider, "
        "voice, or highlighting mode. Include only settings the user explicitly requested."
    )
    input_model = UpdateUiSettingsInput
    output_model = UpdateUiSettingsOutput
    risk_level = RiskLevel.LOW_RISK
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 5_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        del inp, ctx

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        del ctx
        data = UpdateUiSettingsInput.model_validate(inp.model_dump(exclude_unset=True))
        return UpdateUiSettingsOutput(
            **data.model_dump(exclude_unset=True),
            message="Updated the requested website settings.",
        )
