from javaxFlash import Client, Config

client = Client(
    Config(
        tavily_api_key="your-tavily-api-key",
        auto_search=True,
        search_tool_name="tavily",
    )
)

response = client.flash(
    "What is the latest Python release and what changed?",
    skills="search",
)
print(response.text)

response = client.flash(
    "Summarize this page: https://docs.python.org/3/whatsnew/",
    skills=["extract"],
)
print(response.text)
