from pathlib import Path
import sys

from lunox.display import show_response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunox import Client, Config, ProviderError


def main() -> None:
    cfg = Config(
        provider="gemini",
        timeout=20.0,
        retries=2,
        fallback=True,
        custom_instruction="You are Lunox. Answer clearly, briefly, and helpfully for beginner Python developers.",
    )
    cfg.set_retry_policy(backoff=0.5, backoff_rate=2.0)
    client = Client(cfg=cfg)
    try:
        res = client.ask("jelaskan apa itu bahasa pemrograman")
    except ProviderError as err:
        print(f"Example could not reach provider: {err}")
        return

    print("Config provider:", cfg.provider)
    print("Config timeout:", cfg.timeout)
    print("Custom instruction:", cfg.custom_instruction)
    print("Provider:", res.provider)
    print("Model:", res.model)
    print("Reason:", res.reason)
    show_response(res, delay=0.05)


if __name__ == "__main__":
    main()
