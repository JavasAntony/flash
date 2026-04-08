from javaxFlash import Client


client = Client()

auto_response = client.flash("What is Python used for?")
print("Auto routed to:", auto_response.provider)

reasoning_response = client.flash(
    "Compare a monolith and microservices for a growing SaaS product.",
    mode="reasoning",
)
print("Reasoning mode provider:", reasoning_response.provider)

forced_response = client.flash(
    "Use the flash provider directly.",
    provider="flash",
)
print("Forced provider:", forced_response.provider)
