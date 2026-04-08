from .client import AIClient, FlashClient
from .config import AIClientConfig, FlashConfig
from .errors import (
    FlashError,
    ProviderError,
    ProviderNotFoundError,
    RetryExhaustedError,
    SchemaValidationError,
    TimeoutError,
    ToolExecutionError,
)
from .models import AIResponse, FlashResponse
from .schema import Schema
from .tools import (
    BaseTool,
    TavilyTool,
    Tool,
    ToolRegistry,
    ToolResult,
)

__version__ = "3.0.0"

Client = FlashClient
Config = FlashConfig
Response = FlashResponse
JsonSchema = Schema

__all__ = [
    "AIClient",
    "AIClientConfig",
    "AIResponse",
    "BaseTool",
    "Client",
    "Config",
    "FlashClient",
    "FlashConfig",
    "FlashError",
    "FlashResponse",
    "JsonSchema",
    "ProviderError",
    "ProviderNotFoundError",
    "Response",
    "RetryExhaustedError",
    "Schema",
    "SchemaValidationError",
    "TavilyTool",
    "TimeoutError",
    "Tool",
    "ToolExecutionError",
    "ToolRegistry",
    "ToolResult",
]
