from javaxFlash import Client, Config, RetryExhaustedError, TimeoutError

config = Config(
    timeout=20.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_multiplier=2.0,
    jitter=0.2,
    fallback_enabled=True,
    debug=True,
)

client = Client(config=config)

try:
    response = client.flash("Summarize retry strategies for HTTP clients.")
    print(response.text)
    print("Retries used:", response.retry_count)
except (TimeoutError, RetryExhaustedError) as exc:
    print("Request failed:", exc)
