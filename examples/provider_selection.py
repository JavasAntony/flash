from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from javaxFlash import Client, ProviderError


def main() -> None:
    client = Client()
    try:
        auto = client.flash("What is Python used for?")
        print("Auto:", auto.provider)

        deep = client.flash(
            "Compare a monolith and microservices for a growing SaaS product.",
            mode="reasoning",
        )
        print("Reasoning:", deep.provider)

        forced = client.flash("Use the flash provider directly.", provider="flash")
        print("Forced:", forced.provider)
    except ProviderError as err:
        print(f"Example could not reach provider: {err}")


if __name__ == "__main__":
    main()
