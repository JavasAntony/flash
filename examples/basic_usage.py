from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from javaxFlash import Client, ProviderError


def main() -> None:
    client = Client()
    try:
        res = client.flash("Explain the difference between REST and GraphQL in simple terms.")
    except ProviderError as err:
        print(f"Example could not reach provider: {err}")
        return

    print("Provider:", res.provider)
    print("Model:", res.model)
    print("Reason:", res.reason)
    print("Text:", res.text)


if __name__ == "__main__":
    main()
