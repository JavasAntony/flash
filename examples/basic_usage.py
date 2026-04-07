from flash import FlashClient, FlashConfig
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table


console = Console()


def show_response(response) -> None:
    table = Table(show_header=False, box=None)
    table.add_row("[bold cyan]Text[/bold cyan]", response.text or "-")
    table.add_row("[bold cyan]Model[/bold cyan]", getattr(response, "model_used", "-") or "-")
    table.add_row("[bold cyan]Provider[/bold cyan]", getattr(response, "provider", "-") or "-")
    table.add_row("[bold cyan]Route Reason[/bold cyan]", getattr(response, "route_reason", "-") or "-")
    console.print(Panel(table, title="[bold green]Flash Response[/bold green]", expand=False))


def main() -> None:
    console.print(Panel.fit("[bold yellow]Flash Client Example[/bold yellow]"))

    config = FlashConfig(
        debug=True,
        default_system_instruction="You are Flash, a concise and practical AI assistant.",
    )
    client = FlashClient(config=config)

    while True:
        user_input = Prompt.ask("\n[bold blue]Masukkan pertanyaan[/bold blue] ([green]ketik 'exit' untuk keluar[/green])")
        if user_input.lower() in {"exit", "quit"}:
            console.print("[bold red]Keluar dari program.[/bold red]")
            break

        mode = Prompt.ask(
            "[bold blue]Pilih mode[/bold blue]",
            choices=["fast", "reasoning", "auto"],
            default="auto",
        )

        try:
            options = {"auto_route": True} if mode == "auto" else {"mode": mode}
            response = client.flash(user_input, **options)

            show_response(response)

        except Exception as e:
            console.print(Panel.fit(f"[bold red]Error[/bold red]\n{e}", border_style="red"))


if __name__ == "__main__":
    main()
