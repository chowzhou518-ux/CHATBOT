"""LangGraph-based chatbot agent for parking reservations using LangChain 1.0."""

import time
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.core.rag_engine_standard import StandardRAGEngine as RAGEngine, get_standard_rag_engine as get_rag_engine
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
    user_input: str
    response: str


class LangGraphParkingAgent:
    """LangGraph-based chatbot agent using LangChain 1.0."""

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

        # Pass db_manager to the reservation collector
        self.reservation_collector = ReservationDataCollector(db_manager=self.parking_tools.db_manager)
        self.in_reservation_flow = False

        # Build LangGraph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""

        # Node functions
        def classify_intent_node(state: AgentState) -> AgentState:
            """Classify user intent."""
            user_input = state.get("user_input", "")
            intent = self._classify_intent(user_input)
            state["current_intent"] = intent
            return state

        def guardrail_node(state: AgentState) -> AgentState:
            """Apply input guardrails."""
            user_input = state.get("user_input", "")
            processed_input, error = self.guardrails.process_input(user_input)

            if error:
                state["guardrail_violations"] += 1
                state["response"] = error
                state["current_intent"] = Intent.UNKNOWN
            else:
                state["user_input"] = processed_input

            return state

        def information_node(state: AgentState) -> AgentState:
            """Handle information queries using RAG."""
            user_input = state.get("user_input", "")
            result = self.rag_engine.query(user_input, use_history=True)
            state["response"] = result.answer
            return state

        def availability_node(state: AgentState) -> AgentState:
            """Handle availability queries."""
            user_input = state.get("user_input", "").lower()
            space_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]

            mentioned_type = None
            for space_type in space_types:
                if space_type in user_input or space_type.replace("_", " ") in user_input:
                    mentioned_type = space_type
                    break

            if mentioned_type:
                state["response"] = self.parking_tools.check_availability(mentioned_type)
            else:
                state["response"] = self.parking_tools.get_all_availability()
            return state

        def pricing_node(state: AgentState) -> AgentState:
            """Handle pricing queries."""
            user_input = state.get("user_input", "").lower()
            space_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]

            mentioned_type = None
            for space_type in space_types:
                if space_type in user_input or space_type.replace("_", " ") in user_input:
                    mentioned_type = space_type
                    break

            state["response"] = self.parking_tools.get_prices(mentioned_type)
            return state

        def reservation_node(state: AgentState) -> AgentState:
            """Handle reservation data collection."""
            user_input = state.get("user_input", "")
            result = self.reservation_collector.process_input(user_input)

            if result["status"] == "complete":
                self.in_reservation_flow = False

            if result["status"] == "collecting":
                message = result["message"]
                if result.get("collected"):
                    message = f"{result['collected']}\n\n{message}"
                state["response"] = message
            elif result["status"] == "complete":
                state["response"] = result["message"]
            elif result["status"] == "error":
                state["response"] = f"Sorry, {result['error']}\n\n{self.reservation_collector.get_current_prompt()}"
            else:
                state["response"] = "I'm processing your reservation request."
            return state

        def output_guardrail_node(state: AgentState) -> AgentState:
            """Apply output guardrails."""
            response = state.get("response", "")
            final_response, warning = self.guardrails.process_output(response)

            if warning:
                final_response = f"{final_response}\n{warning}"

            state["response"] = final_response
            return state

        def update_history_node(state: AgentState) -> AgentState:
            """Update conversation history."""
            user_input = state.get("user_input", "")
            response = state.get("response", "")

            state["messages"].append({"role": "user", "content": user_input})
            state["messages"].append({"role": "assistant", "content": response})
            state["last_response_time"] = time.time()

            return state

        # Routing function
        def route_intent(state: AgentState) -> Literal["information", "availability", "pricing", "reservation", END]:
            """Route to appropriate handler based on intent."""
            if state.get("guardrail_violations", 0) > 0:
                # Guardrail violation triggered, end with error response
                return END

            intent = state.get("current_intent", Intent.UNKNOWN)

            if intent == Intent.RESERVATION:
                return "reservation"
            elif intent == Intent.AVAILABILITY:
                return "availability"
            elif intent == Intent.PRICING:
                return "pricing"
            else:
                return "information"

        # Build the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("guardrail", guardrail_node)
        workflow.add_node("classify", classify_intent_node)
        workflow.add_node("information", information_node)
        workflow.add_node("availability", availability_node)
        workflow.add_node("pricing", pricing_node)
        workflow.add_node("reservation", reservation_node)
        workflow.add_node("output_guardrail", output_guardrail_node)
        workflow.add_node("update_history", update_history_node)

        # Set entry point
        workflow.set_entry_point("guardrail")

        # Add edges
        workflow.add_edge("guardrail", "classify")
        workflow.add_conditional_edges(
            "classify",
            route_intent,
            {
                "information": "information",
                "availability": "availability",
                "pricing": "pricing",
                "reservation": "reservation",
                END: END
            }
        )
        workflow.add_edge("information", "output_guardrail")
        workflow.add_edge("availability", "output_guardrail")
        workflow.add_edge("pricing", "output_guardrail")
        workflow.add_edge("reservation", "output_guardrail")
        workflow.add_edge("output_guardrail", "update_history")
        workflow.add_edge("update_history", END)

        return workflow.compile()

    def _classify_intent(self, user_input: str) -> Intent:
        """Classify user intent."""
        input_lower = user_input.lower()

        # Check if in reservation flow
        if self.in_reservation_flow:
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

        return Intent.INFORMATION

    def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user message through the LangGraph agent.

        Args:
            user_input: User's message

        Returns:
            Dict with 'response', 'intent', 'latency', etc.
        """
        start_time = time.time()

        # Initialize state
        initial_state: AgentState = {
            "messages": [],
            "current_intent": Intent.UNKNOWN,
            "reservation_data": {},
            "collection_step": 0,
            "guardrail_violations": 0,
            "last_response_time": 0,
            "user_input": user_input,
            "response": ""
        }

        # Run the graph
        try:
            final_state = self.graph.invoke(initial_state)
        except Exception as e:
            return {
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "intent": Intent.UNKNOWN,
                "latency": time.time() - start_time,
                "error": True
            }

        return {
            "response": final_state.get("response", ""),
            "intent": final_state.get("current_intent", Intent.UNKNOWN),
            "latency": time.time() - start_time,
            "state": final_state
        }

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        # In a real implementation, you'd retrieve this from the state
        return []

    def clear_history(self) -> None:
        """Clear conversation history and reset state."""
        self.rag_engine.clear_history()
        self.in_reservation_flow = False
        self.reservation_collector.reset()

    def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "guardrail_stats": self.guardrails.get_statistics(),
            "current_intent": self.in_reservation_flow,
            "in_reservation_flow": self.in_reservation_flow
        }


class SimpleParkingChatbot:
    """Simplified chatbot without full LangGraph dependency."""

    def __init__(self):
        """Initialize simplified chatbot."""
        self.parking_tools = get_parking_tools()
        self.guardrails = get_guardrail_handler()
        self.in_reservation_mode = False
        self.reservation_collector = ReservationDataCollector(db_manager=self.parking_tools.db_manager)

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


def get_chatbot_agent() -> LangGraphParkingAgent:
    """Get LangGraph chatbot agent instance."""
    return LangGraphParkingAgent()


def get_simple_chatbot() -> SimpleParkingChatbot:
    """Get simple chatbot instance."""
    return SimpleParkingChatbot()


# Alias for compatibility with main.py
get_langgraph_agent = get_chatbot_agent
