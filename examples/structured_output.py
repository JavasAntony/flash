from javaxFlash import Client, JsonSchema


task_schema = JsonSchema(
    name="task_summary",
    fields={
        "title": str,
        "priority": str,
        "action_items": [str],
    },
)

client = Client()
response = client.flash(
    "Turn this into a compact task plan for backend cleanup.",
    schema=task_schema,
)

print(response.structured_output)
