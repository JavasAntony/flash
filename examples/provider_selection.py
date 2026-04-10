from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, ProviderError


def main() -> None:
    client = Client()
    try:
        auto = client.ask("What is Python used for?")
        print("Auto provider:", auto.provider)

        deep = client.ask(
            "Analyze this architecture tradeoff between monolith and microservices.",
            provider="deepseek",
        )
        print("Deepseek:", deep.text)

        forced = client.ask("Use the Gemini provider directly.", provider="gemini")
        print("Gemini:", forced.text)
    except ProviderError as err:
        print(f"Example could not reach provider: {err}")


if __name__ == "__main__":
    main()
