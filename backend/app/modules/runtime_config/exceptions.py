"""Typed domain exceptions for the runtime config module."""


class RuntimeConfigError(Exception):
    """Base for runtime config errors."""


class UnknownSettingKeyError(RuntimeConfigError):
    """Key is not in the runtime-tunable whitelist."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Unknown or non-overridable setting: {key}")


class OverrideNotFoundError(RuntimeConfigError):
    """No stored override exists for a whitelisted key."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"No override stored for setting: {key}")


class SettingValueInvalidError(RuntimeConfigError):
    """Value fails the field's type/constraint validation."""

    def __init__(self, key: str, message: str) -> None:
        self.key = key
        super().__init__(f"Invalid value for {key}: {message}")
