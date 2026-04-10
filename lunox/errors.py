from __future__ import annotations


class AppError(Exception):
    """Base error for Lunox."""


class ProviderError(AppError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


class MissingProviderError(ProviderError):
    pass


class TimeoutError(ProviderError):
    pass


class RetryError(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
        tries: int = 0,
    ) -> None:
        super().__init__(message, provider=provider, status=status)
        self.tries = tries


class SchemaError(AppError):
    pass


class ToolError(AppError):
    pass
