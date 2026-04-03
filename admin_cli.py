#!/usr/bin/env python3
"""Administrator CLI for managing parking reservations."""

import sys
import argparse
from datetime import datetime

from src.chatbot.admin_agent import get_admin_agent
from src.chatbot.escalation import get_escalation_manager
from src.data.reservation_manager import get_reservation_manager


def print_header():
    """Print the CLI header."""
    print("\n" + "="*80)
    print("🚗 PARKING RESERVATION ADMINISTRATOR CONSOLE")
    print("="*80)
    print()


def print_menu():
    """Print the main menu."""
    print("\n📋 Available Commands:")
    print("  1. list              - List all pending reservations")
    print("  2. details <id>      - Get details of a specific reservation")
    print("  3. approve <id>      - Approve a reservation")
    print("  4. reject <id>       - Reject a reservation")
    print("  5. stats             - Show reservation statistics")
    print("  6. cleanup           - Clean up expired reservations")
    print("  7. help              - Show this menu")
    print("  8. quit/exit         - Exit the console")
    print()


def main():
    """Main administrator CLI entry point."""
    parser = argparse.ArgumentParser(description="Parking Reservation Administrator Console")
    parser.add_argument("--admin-mode", action="store_true", help="Start in admin mode")
    args = parser.parse_args()

    # Initialize components
    admin_agent = get_admin_agent()
    escalation_manager = get_escalation_manager()
    reservation_manager = get_reservation_manager()

    print_header()
    print("✅ Administrator console initialized")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print_menu()

    # Main command loop
    while True:
        try:
            # Get user input
            user_input = input("\n🔧 admin> ").strip()

            if not user_input:
                continue

            # Handle exit commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Handle help
            if user_input.lower() in ["help", "h", "?", "menu"]:
                print_menu()
                continue

            # Process command
            response = admin_agent.process_message(user_input)
            print("\n" + response)

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            print("👋 Goodbye!")
            break

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again or type 'help' for available commands.")


if __name__ == "__main__":
    main()
