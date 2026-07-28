"""Tool domain errors."""

from __future__ import annotations


class ToolError(Exception):
    """Base tool error."""


class ToolNotFoundError(ToolError):
    """Unknown tool name."""


class ToolAuthzError(ToolError):
    """Caller is not allowed to run this tool / access this resource."""


class ToolValidationError(ToolError):
    """Args failed input schema validation."""


class ToolModeBlockedError(ToolError):
    """Tool blocked by assistant mode (e.g. external in internal_only)."""


class ToolConfirmationRequiredError(ToolError):
    """Tool needs HITL confirmation before execute (B3.3+)."""
