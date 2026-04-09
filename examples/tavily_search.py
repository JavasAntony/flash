from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from javaxFlash import Client, Config, ProviderError, ToolError


def main() -> None:
    client = Client(
        cfg=Config(
            tavily_key="your-tavily-api-key",
            search_tool="tavily",
        )
    )

    try:
        res = client.ask(
            "What is the latest Python release and what changed?",
            skills="search",
        )
        print(res.text)

        res = client.flash(
            "Summarize this page: https://docs.python.org/3/whatsnew/",
            skills=["extract"],
        )
        print(res.text)
    except (ProviderError, ToolError) as err:
        print(f"Example could not complete Tavily flow: {err}")


if __name__ == "__main__":
    main()
