"""Audio domain exceptions."""


class UnknownProviderError(Exception):
    """Requested TTS provider is not registered."""


class SynthesisError(Exception):
    """TTS synthesis failed."""


class TextTooLongError(Exception):
    """Input text exceeds synthesize limits."""
