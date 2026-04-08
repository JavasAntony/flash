from javaxFlash import Client, Config


client = Client(
    Config(
        tavily_api_key="your-tavily-api-key",
        search_tool_name="tavily",
    )
)

client.use_tavily()

search_context = client.search("latest Python release", limit=3)
print(search_context)

extract_context = client.extract("https://docs.python.org/3/whatsnew/")
print(extract_context)

crawl_context = client.crawl(
    "https://docs.python.org/3/",
    instructions="Focus on release notes and migration guidance.",
)
print(crawl_context)
