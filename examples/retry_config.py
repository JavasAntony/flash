from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, Config, ProviderError, RetryError, TimeoutError

cfg = Config(
    timeout=20.0,
    retries=3,
    backoff=0.5,
    backoff_rate=2.0,
    jitter=0.2,
    fallback=True,
    debug=True,
)


def main() -> None:
    client = Client(cfg=cfg)
    try:
        res = client.ask("Summarize retry strategies for HTTP clients.")
        print(res.text)
        print("Retries used:", res.retries)
    except (TimeoutError, RetryError, ProviderError) as err:
        print("Request failed:", err)


if __name__ == "__main__":
    main()
