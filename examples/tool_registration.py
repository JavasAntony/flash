from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, Config, ProviderError, ToolError


def project_info() -> dict[str, str]:
    return {
        "title": "Lunox",
        "content": "Lunox is a compact client for multi-provider prompting with routing and tools.",
    }


def main() -> None:
    client = Client(cfg=Config())
    client.add_fn("project_info", project_info)

    try:
        res = client.ask("Summarize the current project focus.", tool_calls={"project_info": {}})
    except (ProviderError, ToolError) as err:
        print(f"Example failed: {err}")
        return

    print(res.text)


if __name__ == "__main__":
    main()
