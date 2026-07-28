"""HITL form helpers: merge user values and build confirmation_request form."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from pydantic_core import PydanticUndefined

from app.modules.tools.base import BaseTool
from app.modules.tools.exceptions import ToolValidationError


def merge_confirmed_args(
    tool: BaseTool,
    proposed: dict[str, Any],
    values: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge user form values into the frozen proposal; re-validate input_model."""
    merged = dict(proposed)
    if values:
        schema = tool.confirmation_schema
        if schema is None:
            raise ToolValidationError("tool has no confirmation form")
        try:
            cleaned = schema.model_validate(values).model_dump(exclude_unset=True)
        except ValidationError as exc:
            raise ToolValidationError(str(exc)) from exc
        merged.update(cleaned)
    try:
        return tool.input_model.model_validate(merged).model_dump(mode="json")
    except ValidationError as exc:
        raise ToolValidationError(str(exc)) from exc


def build_form_payload(
    tool: BaseTool,
    proposed: dict[str, Any],
) -> dict[str, Any] | None:
    """JSON-serializable form descriptor for confirmation_request, or None."""
    schema = tool.confirmation_schema
    if schema is None:
        return None
    fields: list[dict[str, Any]] = []
    for name, field in schema.model_fields.items():
        default: Any = proposed.get(name)
        if default is None and field.default is not PydanticUndefined:
            default = field.default
        fields.append(
            {
                "name": name,
                "label": _label(name, field.description),
                "type": _field_type(field.annotation),
                "required": field.is_required(),
                "default": default,
                **_numeric_bounds(field),
            }
        )
    return {"fields": fields}


def _label(name: str, description: str | None) -> str:
    if description:
        return description
    return name.replace("_", " ").capitalize()


def _field_type(annotation: object) -> str:
    text = str(annotation)
    if "int" in text:
        return "integer"
    if "float" in text:
        return "number"
    if "bool" in text:
        return "boolean"
    return "string"


def _numeric_bounds(field: object) -> dict[str, int | float]:
    """Extract ge/le/gt/lt metadata for number inputs."""
    meta = getattr(field, "metadata", None) or ()
    out: dict[str, int | float] = {}
    for item in meta:
        ge = getattr(item, "ge", None)
        gt = getattr(item, "gt", None)
        le = getattr(item, "le", None)
        lt = getattr(item, "lt", None)
        if ge is not None:
            out["min"] = ge
        elif gt is not None:
            out["min"] = gt + 1 if isinstance(gt, int) else gt
        if le is not None:
            out["max"] = le
        elif lt is not None:
            out["max"] = lt - 1 if isinstance(lt, int) else lt
    return out
