from javaxFlash import Client

def main() -> None:
    client = Client()
    response = client.flash("Explain the difference between REST and GraphQL in simple terms.")

    print("Provider:", response.provider)
    print("Model:", response.model_used)
    print("Route reason:", response.route_reason)
    print("Text:", response.text)


if __name__ == "__main__":
    main()
