from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from javaxFlash import Client, ProviderError, SchemaError


@dataclass
class Ticket:
    title: str
    priority: str


def main() -> None:
    client = Client()
    try:
        res = client.flash("Summarize this bug report.", schema=Ticket)
    except (ProviderError, SchemaError) as err:
        print(f"Example could not complete: {err}")
        return
    print(res.data)


if __name__ == "__main__":
    main()
