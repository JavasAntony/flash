from __future__ import annotations


class FlashError(Exception):
    """Base exception for javaxFlash."""


class ProviderError(FlashError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ProviderNotFoundError(ProviderError):
    pass


class TimeoutError(ProviderError):
    pass


class RetryExhaustedError(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        attempts: int = 0,
    ):
        super().__init__(message, provider=provider, status_code=status_code)
        self.attempts = attempts


class SchemaValidationError(FlashError):
    pass


class ToolExecutionError(FlashError):
    pass
