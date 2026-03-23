"""LangGraph-based chatbot agent for parking reservations."""

import time
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
from enum import Enum

from src.core.rag_engine import RAGEngine, get_rag_engine
from src.chatbot.tools import ParkingTools, ReservationDataCollector, get_parking_tools
from src.guards.railguard import GuardRailHandler, get_guardrail_handler
from src.config.settings import get_settings


class Intent(str, Enum):
    """User intent types."""
    INFORMATION = "information"
    RESERVATION = "reservation"
    AVAILABILITY = "availability"
    PRICING = "pricing"
    UNKNOWN = "unknown"


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    messages: List[Dict[str, str]]
    current_intent: Intent
    reservation_data: Dict[str, Any]
    collection_step: int
    guardrail_violations: int
    last_response_time: float


class ParkingChatbotAgent:
    """LangGraph-based chatbot agent."""

    def __init__(
        self,
        rag_engine: Optional[RAGEngine] = None,
        parking_tools: Optional[ParkingTools] = None,
        guardrail_handler: Optional[GuardRailHandler] = None,
    ):
        """Initialize the chatbot agent."""
        self.rag_engine = rag_engine or get_rag_engine()
        self.parking_tools = parking_tools or get_parking_tools()
        self.guardrails = guardrail_handler or get_guardrail_handler()

        self.reservation_collector = ReservationDataCollector()
        self.in_reservation_flow = False

        # Initialize state
        self.state: AgentState = {
            "messages": [],
            "current_intent": Intent.UNKNOWN,
            "reservation_data": {},
            "collection_step": 0,
            "guardrail_violations": 0,
            "last_response_time": 0,
        }

    def classify_intent(self, user_input: str) -> Intent:
        """
        Classify user intent.

        Args:
            user_input: User's message

        Returns:
            Classified intent.
        """
        input_lower = user_input.lower()

        # Check if in reservation flow
        if self.in_reservation_flow:
            # User might want to cancel
            if any(word in input_lower for word in ["cancel", "stop", "never mind", "abort"]):
                self.in_reservation_flow = False
                self.reservation_collector.reset()
                return Intent.INFORMATION
            return Intent.RESERVATION

        # Reservation indicators
        if any(word in input_lower for word in [
            "reserve", "book", "reservation", "booking", "schedule"
        ]):
            self.in_reservation_flow = True
            self.reservation_collector.reset()
            return Intent.RESERVATION

        # Availability indicators
        if any(word in input_lower for word in [
            "available", "availability", "space available", "how many", "is there space"
        ]):
            return Intent.AVAILABILITY

        # Pricing indicators
        if any(word in input_lower for word in [
            "price", "cost", "rate", "how much", "fee", "charge", "cheap", "expensive"
        ]):
            return Intent.PRICING

        # Default to information query
        return Intent.INFORMATION

    def handle_information(self, user_input: str) -> str:
        """Handle general information queries."""
        # Use RAG for knowledge base queries
        result = self.rag_engine.query(user_input, use_history=True)
        return result.answer

    def handle_availability(self, user_input: str) -> str:
        """Handle availability queries."""
        # Check if specific space type is mentioned
        input_lower = user_input.lower()
        space_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]

        mentioned_type = None
        for space_type in space_types:
            if space_type in input_lower or space_type.replace("_", " ") in input_lower:
                mentioned_type = space_type
                break

        if mentioned_type:
            return self.parking_tools.check_availability(mentioned_type)
        else:
            return self.parking_tools.get_all_availability()

    def handle_pricing(self, user_input: str) -> str:
        """Handle pricing queries."""
        # Check if specific space type is mentioned
        input_lower = user_input.lower()
        space_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]

        mentioned_type = None
        for space_type in space_types:
            if space_type in input_lower or space_type.replace("_", " ") in input_lower:
                mentioned_type = space_type
                break

        return self.parking_tools.get_prices(mentioned_type)

    def handle_reservation(self, user_input: str) -> str:
        """Handle reservation data collection."""
        # Process the input through the collector
        result = self.reservation_collector.process_input(user_input)

        if result["status"] == "collecting":
            # Still collecting data
            message = result["message"]
            if result.get("collected"):
                message = f"{result['collected']}\n\n{message}"
            return message

        elif result["status"] == "complete":
            # Collection complete, submit reservation
            self.in_reservation_flow = False
            return result["message"]

        elif result["status"] == "error":
            # Error in validation, re-prompt for same field
            return f"Sorry, {result['error']}\n\n{self.reservation_collector.get_current_prompt()}"

        return "I'm processing your reservation request."

    def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user message through the agent.

        Args:
            user_input: User's message

        Returns:
            Dict with 'response', 'intent', 'latency', etc.
        """
        start_time = time.time()

        # Apply input guardrails
        processed_input, input_error = self.guardrails.process_input(user_input)

        if input_error:
            return {
                "response": input_error,
                "intent": Intent.UNKNOWN,
                "guardrail_violation": True,
                "latency": time.time() - start_time,
            }

        # Classify intent
        intent = self.classify_intent(processed_input)
        self.state["current_intent"] = intent

        # Route to appropriate handler
        if intent == Intent.RESERVATION:
            response = self.handle_reservation(processed_input)
        elif intent == Intent.AVAILABILITY:
            response = self.handle_availability(processed_input)
        elif intent == Intent.PRICING:
            response = self.handle_pricing(processed_input)
        else:
            response = self.handle_information(processed_input)

        # Apply output guardrails
        final_response, output_warning = self.guardrails.process_output(response)

        if output_warning:
            final_response = f"{final_response}\n{output_warning}"

        # Update state
        self.state["messages"].append({"role": "user", "content": user_input})
        self.state["messages"].append({"role": "assistant", "content": final_response})
        self.state["last_response_time"] = time.time() - start_time

        return {
            "response": final_response,
            "intent": intent,
            "latency": self.state["last_response_time"],
            "state": self.state.copy(),
        }

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.state["messages"]

    def clear_history(self) -> None:
        """Clear conversation history and reset state."""
        self.state["messages"] = []
        self.state["current_intent"] = Intent.UNKNOWN
        self.state["guardrail_violations"] = 0
        self.rag_engine.clear_history()
        self.in_reservation_flow = False
        self.reservation_collector.reset()

    def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "total_messages": len(self.state["messages"]) // 2,
            "guardrail_stats": self.guardrails.get_statistics(),
            "current_intent": self.state["current_intent"],
            "in_reservation_flow": self.in_reservation_flow,
        }


class SimpleParkingChatbot:
    """Simplified chatbot without full LangGraph dependency."""

    def __init__(self):
        """Initialize simplified chatbot."""
        self.parking_tools = get_parking_tools()
        self.guardrails = get_guardrail_handler()
        self.in_reservation_mode = False
        self.reservation_collector = ReservationDataCollector()

    def chat(self, user_input: str) -> str:
        """
        Process user input and return response.

        Args:
            user_input: User's message

        Returns:
            Chatbot response.
        """
        # Apply guardrails
        processed_input, input_error = self.guardrails.process_input(user_input)

        if input_error:
            return input_error

        # Check for reservation mode
        if self.in_reservation_mode:
            if any(word in processed_input.lower() for word in ["cancel", "stop", "abort"]):
                self.in_reservation_mode = False
                self.reservation_collector.reset()
                return "Reservation cancelled. How else can I help you?"

            result = self.reservation_collector.process_input(processed_input)

            if result["status"] == "complete":
                self.in_reservation_mode = False
                return result["message"]
            elif result["status"] == "error":
                return f"Sorry, {result['error']}\n\n{self.reservation_collector.get_current_prompt()}"
            else:
                message = result["message"]
                if result.get("collected"):
                    message = f"{result['collected']}\n\n{message}"
                return message

        # Classify intent
        input_lower = processed_input.lower()

        # Reservation request
        if any(word in input_lower for word in ["reserve", "book", "reservation", "booking"]):
            self.in_reservation_mode = True
            return self.reservation_collector.get_current_prompt()

        # Availability query
        if any(word in input_lower for word in ["available", "availability", "how many"]):
            space_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]
            mentioned = None
            for st in space_types:
                if st in input_lower:
                    mentioned = st
                    break
            return self.parking_tools.check_availability(mentioned) if mentioned else self.parking_tools.get_all_availability()

        # Pricing query
        if any(word in input_lower for word in ["price", "cost", "rate", "how much"]):
            return self.parking_tools.get_prices()

        # Location query
        if any(word in input_lower for word in ["where", "location", "address", "direction"]):
            return self.parking_tools.get_location_info()

        # Hours query
        if any(word in input_lower for word in ["hour", "open", "close", "when"]):
            return self.parking_tools.get_working_hours()

        # Payment query
        if "payment" in input_lower or "pay" in input_lower:
            return self.parking_tools.get_payment_methods()

        # Rules query
        if "rule" in input_lower or "policy" in input_lower:
            return self.parking_tools.get_rules_summary()

        # Default: general info from knowledge base
        topic = input_lower.split()[0] if input_lower else "general"
        return self.parking_tools.get_parking_info(topic)


def get_chatbot_agent() -> ParkingChatbotAgent:
    """Get chatbot agent instance."""
    return ParkingChatbotAgent()


def get_simple_chatbot() -> SimpleParkingChatbot:
    """Get simple chatbot instance."""
    return SimpleParkingChatbot()
