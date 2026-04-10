from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, ProviderError, Schema, SchemaError


def main() -> None:
    client = Client()
    schema = Schema(name="ticket", fields={"title": str, "priority": str})
    try:
        res = client.ask("Summarize this bug report.", schema=schema)
    except (ProviderError, SchemaError) as err:
        print(f"Example could not complete: {err}")
        return
    print(res.data)


if __name__ == "__main__":
    main()
