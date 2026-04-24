#!/usr/bin/env python3
"""Main entry point for the parking reservation system with LangGraph orchestration."""

import sys
import argparse

def run_orchestrator():
    """Run the system with LangGraph orchestration."""
    from src.orchestration.graph import get_orchestrator

    orchestrator = get_orchestrator()
    orchestrator.run_interactive_session()


def run_simple_chatbot():
    """Run the simple chatbot without full orchestration."""
    from src.chatbot.agent import get_simple_chatbot

    chatbot = get_simple_chatbot()

    print("\n🚗 CityCenter Parking Assistant")
    print("=" * 50)
    print("Commands: 'quit' to exit, 'clear' to clear history")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            if user_input.lower() == "clear":
                print("✓ Conversation cleared\n")
                continue

            response = chatbot.chat(user_input)
            print(f"\nBot: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


def run_admin_console():
    """Run the administrator console with LangChain 1.0 agent."""
    from src.chatbot.admin_agent_final import get_admin_agent

    admin_agent = get_admin_agent()

    print("\n" + "="*80)
    print("🚗 PARKING RESERVATION ADMINISTRATOR CONSOLE (LangChain 1.0)")
    print("="*80)
    print("\n🤖 Powered by LangChain 1.0 + LangGraph")
    print("\nAvailable Commands:")
    print("  list              - List all pending reservations")
    print("  details <id>      - Get details of a specific reservation")
    print("  approve <id>      - Approve a reservation")
    print("  reject <id>       - Reject a reservation")
    print("  stats             - Show reservation statistics")
    print("  help              - Show this menu")
    print("  quit              - Exit the console")
    print("\n")

    while True:
        try:
            user_input = input("🔧 admin> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            if user_input.lower() in ["help", "h", "?"]:
                print("\nAvailable Commands:")
                print("  list              - List all pending reservations")
                print("  details <id>      - Get details of a specific reservation")
                print("  approve <id>      - Approve a reservation")
                print("  reject <id>       - Reject a reservation")
                print("  stats             - Show reservation statistics")
                print("  help              - Show this menu")
                print("  quit              - Exit the console")
                print()
                continue

            response = admin_agent.process_message(user_input)
            print("\n" + response + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again or type 'help' for available commands.\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parking Reservation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run with LangGraph orchestration (default)
  python main.py --simple           # Run simple chatbot
  python main.py --admin            # Run administrator console
  python main.py --test             # Run integration tests
  python main.py --init-db          # Initialize database
        """
    )

    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run simple chatbot without full orchestration"
    )

    parser.add_argument(
        "--admin",
        action="store_true",
        help="Run administrator console"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run integration tests"
    )

    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database and exit"
    )

    parser.add_argument(
        "--orchestrator",
        action="store_true",
        help="Run with LangGraph orchestration (default)"
    )

    args = parser.parse_args()

    # Initialize database if requested
    if args.init_db:
        from src.data.dynamic_data import initialize_database
        print("Initializing database...")
        initialize_database()
        print("Database initialized successfully!")
        return

    # Run tests if requested
    if args.test:
        from tests.integration_test import run_integration_tests
        success = run_integration_tests()
        sys.exit(0 if success else 1)

    # Run appropriate mode
    if args.admin:
        run_admin_console()
    elif args.simple:
        run_simple_chatbot()
    else:
        # Default: orchestrator mode
        run_orchestrator()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
