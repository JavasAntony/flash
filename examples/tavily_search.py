from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, Config, ProviderError, ToolError


def main() -> None:
    client = Client(cfg=Config(tavily_key="your-api-key"))
    try:
        res = client.ask(
            "What is the latest Python release?",
            skills="search",
        )
        print(res.text)
        print("Search query:", res.search_query)

        grounded = client.ask(
            "Use docs https://docs.python.org/3/whatsnew/ to summarize recent changes.",
            skills=["search", "extract"],
        )
        print(grounded.text)
    except (ProviderError, ToolError) as err:
        print(f"Example failed: {err}")


if __name__ == "__main__":
    main()
