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

    client.use_tavily()

    try:
        search_text = client.search("latest Python release", limit=3)
        print(search_text)

        extract_text = client.extract("https://docs.python.org/3/whatsnew/")
        print(extract_text)
    except (ProviderError, ToolError) as err:
        print(f"Example could not use Tavily: {err}")


if __name__ == "__main__":
    main()
