#!/usr/bin/env python3
"""Main entry point for the Parking Chatbot CLI."""

import sys
import os
import argparse
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.config.settings import get_settings
from src.chatbot.agent import get_simple_chatbot
from src.data.dynamic_data import get_db_manager
from src.core.vector_store import initialize_vector_store


class ChatbotCLI:
    """Command-line interface for the parking chatbot."""

    def __init__(self, use_rich: bool = True):
        """Initialize CLI."""
        self.use_rich = use_rich and RICH_AVAILABLE
        if self.use_rich:
            self.console = Console()
        else:
            self.console = None

        self.chatbot = get_simple_chatbot()
        self.running = False

    def print_welcome(self) -> None:
        """Print welcome message."""
        welcome_text = """
# 🚗 CityCenter Parking Assistant

Welcome! I'm your parking assistant. I can help you with:

- **Information**: Location, hours, rules, and facilities
- **Availability**: Check current space availability
- **Pricing**: Get rates for different space types
- **Reservations**: Book a parking space

Type `help` for commands or `quit` to exit.
        """

        if self.use_rich:
            self.console.print(Panel(
                Markdown(welcome_text),
                title="Welcome",
                border_style="blue"
            ))
        else:
            print("=" * 60)
            print("CityCenter Parking Assistant")
            print("=" * 60)
            print(welcome_text)
            print("=" * 60)

    def print_message(self, message: str, style: str = "white") -> None:
        """Print a message to the console."""
        if self.use_rich:
            self.console.print(Panel(
                message,
                border_style=style,
                padding=(0, 1)
            ))
        else:
            print(f"\n[Bot]: {message}\n")

    def print_user_message(self, message: str) -> None:
        """Print user message to console."""
        if self.use_rich:
            self.console.print(f"\n[You] {message}")
        else:
            print(f"\n[You]: {message}")

    def print_stats(self) -> None:
        """Print chatbot statistics."""
        guardrail_stats = self.chatbot.guardrails.get_statistics()

        stats_text = f"""
## Session Statistics

- Total Checks: {guardrail_stats['total_checks']}
- Guardrail Violations: {guardrail_stats['violations']}
- Violation Rate: {guardrail_stats['violation_rate']:.2%}
        """

        if self.use_rich:
            self.console.print(Panel(
                Markdown(stats_text),
                title="Statistics",
                border_style="green"
            ))
        else:
            print("\n" + "=" * 60)
            print("Session Statistics")
            print("=" * 60)
            print(stats_text)

    def handle_command(self, command: str) -> bool:
        """
        Handle special commands.

        Returns:
            True if command was handled, False otherwise.
        """
        command_lower = command.lower().strip()

        if command_lower in ["quit", "exit", "q"]:
            self.running = False
            return True

        elif command_lower == "help":
            help_text = """
## Available Commands

- `help` - Show this help message
- `stats` - Show session statistics
- `clear` - Clear conversation history
- `quit` or `exit` - Exit the chatbot

## Topics you can ask about:

- **Location**: "Where are you located?"
- **Hours**: "What are your hours?"
- **Prices**: "How much does it cost?"
- **Availability**: "Do you have any spaces available?"
- **Reservation**: "I want to make a reservation"
- **Payment**: "What payment methods do you accept?"
            """
            if self.use_rich:
                self.console.print(Panel(Markdown(help_text), border_style="cyan"))
            else:
                print(help_text)
            return True

        elif command_lower == "stats":
            self.print_stats()
            return True

        elif command_lower == "clear":
            self.chatbot.in_reservation_mode = False
            self.chatbot.reservation_collector.reset()
            self.print_message("Conversation context cleared.", "yellow")
            return True

        return False

    def run(self) -> None:
        """Run the interactive chatbot."""
        self.print_welcome()
        self.running = True

        while self.running:
            try:
                # Get user input
                if self.use_rich:
                    user_input = self.console.input("\n[bold cyan]You:[/bold cyan] ")
                else:
                    user_input = input("\nYou: ")

                # Skip empty input
                if not user_input.strip():
                    continue

                # Handle commands
                if self.handle_command(user_input):
                    continue

                # Get chatbot response
                self.print_user_message(user_input)

                response = self.chatbot.chat(user_input)
                self.print_message(response, "blue")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                if self.use_rich:
                    self.console.print(f"\n[red]Error: {str(e)}[/red]")
                else:
                    print(f"\nError: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CityCenter Parking Chatbot - RAG-based assistant"
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        help="Disable rich formatting"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database with sample data"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode"
    )

    args = parser.parse_args()

    # Initialize database if requested
    if args.init_db:
        print("Initializing database...")
        db = get_db_manager()
        db.create_tables()
        db.initialize_sample_data()
        print("Database initialized successfully!")
        return

    # Run chatbot
    try:
        # Initialize components
        print("Starting parking chatbot...")

        # Initialize vector store
        try:
            initialize_vector_store()
        except Exception as e:
            print(f"Warning: Vector store initialization failed: {e}")
            print("Continuing with mock RAG engine...")

        # Start CLI
        cli = ChatbotCLI(use_rich=not args.no_rich)
        cli.run()

    except Exception as e:
        print(f"Failed to start chatbot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
