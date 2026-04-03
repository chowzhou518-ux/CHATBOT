"""LangGraph orchestration for the complete parking reservation system.

This module implements a unified workflow that orchestrates:
1. User interaction (RAG-based chatbot)
2. Reservation data collection
3. Administrator approval (human-in-the-loop)
4. MCP server recording (persistent storage)
"""

import time
from typing import Dict, Any, List, Optional, TypedDict, Literal, Annotated
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.rag_engine import RAGEngine, get_rag_engine
from src.chatbot.tools import get_parking_tools
from src.guards.railguard import GuardRailHandler, get_guardrail_handler
from src.chatbot.escalation import get_escalation_manager
from src.data.reservation_manager import get_reservation_manager
from src.chatbot.admin_agent import get_admin_agent


class WorkflowStage(str, Enum):
    """Workflow stage enumeration."""
    INITIALIZATION = "initialization"
    USER_INTERACTION = "user_interaction"
    DATA_COLLECTION = "data_collection"
    ADMIN_APPROVAL = "admin_approval"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationType(str, Enum):
    """Type of conversation."""
    INFORMATION_QUERY = "information_query"
    RESERVATION_REQUEST = "reservation_request"
    STATUS_CHECK = "status_check"
    ADMIN_COMMAND = "admin_command"


class OrchestrationState(TypedDict):
    """State for the orchestration workflow."""
    # Stage management
    current_stage: WorkflowStage
    conversation_type: ConversationType

    # User interaction
    user_input: str
    user_messages: List[Dict[str, str]]
    bot_response: str

    # Reservation data
    reservation_data: Dict[str, Any]
    collection_step: int

    # Admin approval
    reservation_id: Optional[str]
    admin_decision: Optional[str]
    admin_note: Optional[str]

    # Recording
    recording_success: bool
    recording_error: Optional[str]

    # Metadata
    start_time: float
    last_update: float
    error: Optional[str]
    guardrail_violations: int


class ParkingOrchestrator:
    """Main orchestrator for the parking reservation system using LangGraph."""

    def __init__(
        self,
        rag_engine: Optional[RAGEngine] = None,
        use_memory: bool = True,
    ):
        """Initialize the orchestrator."""
        # Initialize components
        self.rag_engine = rag_engine or get_rag_engine()
        self.parking_tools = get_parking_tools()
        self.guardrails = get_guardrail_handler()
        self.escalation_manager = get_escalation_manager()
        self.reservation_manager = get_reservation_manager()
        self.admin_agent = get_admin_agent()

        # Create the workflow graph
        self.graph = self._build_workflow_graph()

        # Memory checkpoint for conversation persistence
        self.memory = MemorySaver() if use_memory else None

    def _build_workflow_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create graph
        workflow = StateGraph(OrchestrationState)

        # Add nodes
        workflow.add_node("initialize", self._initialize_node)
        workflow.add_node("classify_conversation", self._classify_conversation_node)
        workflow.add_node("handle_information_query", self._handle_information_query_node)
        workflow.add_node("collect_reservation_data", self._collect_reservation_data_node)
        workflow.add_node("escalate_to_admin", self._escalate_to_admin_node)
        workflow.add_node("wait_for_admin_decision", self._wait_for_admin_decision_node)
        workflow.add_node("record_to_mcp", self._record_to_mcp_node)
        workflow.add_node("finalize", self._finalize_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # Define edges
        workflow.set_entry_point("initialize")

        workflow.add_edge("initialize", "classify_conversation")

        # Conditional routing after classification
        workflow.add_conditional_edges(
            "classify_conversation",
            self._route_after_classification,
            {
                "information": "handle_information_query",
                "reservation": "collect_reservation_data",
                "status_check": "handle_information_query",
                "error": "handle_error",
            }
        )

        workflow.add_edge("handle_information_query", "finalize")
        workflow.add_conditional_edges(
            "collect_reservation_data",
            self._route_after_data_collection,
            {
                "collecting": END,  # Need more user input
                "escalate": "escalate_to_admin",
                "error": "handle_error",
            }
        )

        workflow.add_edge("escalate_to_admin", "wait_for_admin_decision")
        workflow.add_conditional_edges(
            "wait_for_admin_decision",
            self._route_after_admin_decision,
            {
                "approved": "record_to_mcp",
                "rejected": "finalize",
                "pending": END,  # Still waiting
                "error": "handle_error",
            }
        )

        workflow.add_edge("record_to_mcp", "finalize")
        workflow.add_edge("handle_error", "finalize")
        workflow.add_edge("finalize", END)

        # Compile graph
        return workflow.compile()

    # ========================================================================
    # Node Implementations
    # ========================================================================

    def _initialize_node(self, state: OrchestrationState) -> OrchestrationState:
        """Initialize the workflow state."""
        state["current_stage"] = WorkflowStage.INITIALIZATION
        state["start_time"] = time.time()
        state["last_update"] = time.time()
        state["guardrail_violations"] = 0
        state["error"] = None

        print(f"\n{'='*80}")
        print(f"🚗 Parking Reservation System - Orchestrator Initialized")
        print(f"{'='*80}\n")

        return state

    def _classify_conversation_node(self, state: OrchestrationState) -> OrchestrationState:
        """Classify the type of conversation."""
        state["current_stage"] = WorkflowStage.USER_INTERACTION

        user_input = state.get("user_input", "")
        input_lower = user_input.lower()

        # Check for admin commands
        if any(word in input_lower for word in ["approve ", "reject ", "list", "stats", "details "]):
            state["conversation_type"] = ConversationType.ADMIN_COMMAND
            # Handle admin command directly
            response = self.admin_agent.process_message(user_input)
            state["bot_response"] = response
            state["current_stage"] = WorkflowStage.COMPLETED
            return state

        # Check for reservation request
        if any(word in input_lower for word in [
            "reserve", "book", "reservation", "booking", "schedule"
        ]):
            state["conversation_type"] = ConversationType.RESERVATION_REQUEST
        elif any(word in input_lower for word in [
            "status", "check status", "my reservation"
        ]):
            state["conversation_type"] = ConversationType.STATUS_CHECK
        else:
            state["conversation_type"] = ConversationType.INFORMATION_QUERY

        print(f"📊 Classified as: {state['conversation_type'].value}")

        return state

    def _handle_information_query_node(self, state: OrchestrationState) -> OrchestrationState:
        """Handle general information queries."""
        state["current_stage"] = WorkflowStage.USER_INTERACTION

        user_input = state.get("user_input", "")

        # Apply guardrails
        processed_input, input_error = self.guardrails.process_input(user_input)

        if input_error:
            state["bot_response"] = input_error
            state["guardrail_violations"] += 1
            return state

        # Use RAG for knowledge base queries
        result = self.rag_engine.query(processed_input, use_history=True)
        state["bot_response"] = result.answer

        # Store in conversation history
        if "user_messages" not in state:
            state["user_messages"] = []

        state["user_messages"].append({"role": "user", "content": user_input})
        state["user_messages"].append({"role": "assistant", "content": state["bot_response"]})

        state["current_stage"] = WorkflowStage.COMPLETED

        return state

    def _collect_reservation_data_node(self, state: OrchestrationState) -> OrchestrationState:
        """Collect reservation data from user."""
        state["current_stage"] = WorkflowStage.DATA_COLLECTION

        # Get reservation data collector
        from src.chatbot.tools import ReservationDataCollector

        if "collector" not in state:
            state["collector"] = ReservationDataCollector()
            state["collection_step"] = 0

        collector = state["collector"]
        user_input = state.get("user_input", "")

        # Process input
        result = collector.process_input(user_input)

        if result["status"] == "collecting":
            state["bot_response"] = result["message"]
            state["collection_step"] += 1
            # Stay in collection mode
            state["current_stage"] = WorkflowStage.DATA_COLLECTION

        elif result["status"] == "complete":
            # Collection complete, prepare for escalation
            reservation_data = result.get("reservation_data", {})
            if not reservation_data:
                reservation_data = collector.get_collected_data()

            state["reservation_data"] = reservation_data
            state["bot_response"] = "Thank you! Your reservation request has been submitted for approval."
            state["current_stage"] = WorkflowStage.ADMIN_APPROVAL

        elif result["status"] == "error":
            state["bot_response"] = f"Sorry, {result['error']}\n\n{collector.get_current_prompt()}"
            # Stay in collection mode
            state["current_stage"] = WorkflowStage.DATA_COLLECTION

        state["last_update"] = time.time()

        return state

    def _escalate_to_admin_node(self, state: OrchestrationState) -> OrchestrationState:
        """Escalate reservation request to administrator."""
        state["current_stage"] = WorkflowStage.ADMIN_APPROVAL

        reservation_data = state.get("reservation_data", {})

        try:
            result = self.escalation_manager.escalate_reservation(
                user_name=reservation_data.get("name", ""),
                user_surname=reservation_data.get("surname", ""),
                car_number=reservation_data.get("car_number", ""),
                start_time=reservation_data.get("start_time", datetime.utcnow()),
                end_time=reservation_data.get("end_time", datetime.utcnow()),
                space_type=reservation_data.get("space_type", "standard"),
                contact_info=reservation_data.get("contact_info", ""),
            )

            if result["success"]:
                state["reservation_id"] = result["reservation_id"]
                state["bot_response"] = f"""✅ Your reservation request has been submitted!

📋 Request ID: {result['reservation_id']}
⏰ Status: Pending Administrator Approval

You will receive a notification once your request is reviewed.
"""
                print(f"\n📤 Escalated to admin: {result['reservation_id']}")
            else:
                state["bot_response"] = f"❌ Failed to submit reservation: {result.get('error', 'Unknown error')}"
                state["error"] = result.get("error")

        except Exception as e:
            state["bot_response"] = f"❌ Error submitting reservation: {str(e)}"
            state["error"] = str(e)

        state["last_update"] = time.time()

        return state

    def _wait_for_admin_decision_node(self, state: OrchestrationState) -> OrchestrationState:
        """Wait for administrator decision (in real system, this would be async)."""
        # For demo purposes, we'll check status immediately
        # In production, this would be a long-polling or webhook-based node

        reservation_id = state.get("reservation_id")

        if not reservation_id:
            state["admin_decision"] = "error"
            return state

        # Check current status
        status_result = self.escalation_manager.check_reservation_status(reservation_id)

        if status_result["success"]:
            status = status_result["status"]

            if status == "approved":
                state["admin_decision"] = "approved"
                state["bot_response"] = "✅ Your reservation has been approved!"
                print(f"\n✅ Admin approved: {reservation_id}")

            elif status == "rejected":
                state["admin_decision"] = "rejected"
                reason = status_result.get("admin_note", "No reason provided")
                state["bot_response"] = f"❌ Your reservation has been rejected.\n\nReason: {reason}"
                state["admin_note"] = reason
                print(f"\n❌ Admin rejected: {reservation_id}")

            else:
                state["admin_decision"] = "pending"
                state["bot_response"] = f"⏳ Your reservation is still pending approval.\n\nRequest ID: {reservation_id}"
        else:
            state["admin_decision"] = "error"
            state["error"] = status_result.get("error")

        state["last_update"] = time.time()

        return state

    def _record_to_mcp_node(self, state: OrchestrationState) -> OrchestrationState:
        """Record approved reservation to MCP server."""
        state["current_stage"] = WorkflowStage.RECORDING

        reservation_id = state.get("reservation_id")
        reservation_data = state.get("reservation_data", {})

        if not reservation_id or not reservation_data:
            state["recording_success"] = False
            state["recording_error"] = "Missing reservation data"
            return state

        try:
            # Get full reservation details
            reservation = self.reservation_manager.get_reservation(reservation_id)

            if not reservation:
                state["recording_success"] = False
                state["recording_error"] = "Reservation not found"
                return state

            # Save to MCP server
            from src.mcp.server import save_approved_reservation

            success = save_approved_reservation(
                name=reservation.user_name,
                surname=reservation.user_surname,
                car_number=reservation.car_number,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                reservation_id=reservation.reservation_id,
                space_type=reservation.space_type,
                contact_info=reservation.contact_info,
                mcp_server_url="http://localhost:8001",
            )

            state["recording_success"] = success

            if success:
                state["bot_response"] = f"""{state.get('bot_response', '')}

✅ Reservation has been recorded to our system.
📁 Your reservation is now confirmed!

Thank you for using our parking service!
"""
                print(f"\n💾 Recorded to MCP: {reservation_id}")
            else:
                state["recording_error"] = "Failed to write to MCP server"
                state["bot_response"] = f"""{state.get('bot_response', '')}

⚠️  Note: There was an issue saving to our records, but your reservation is approved.
"""

        except Exception as e:
            state["recording_success"] = False
            state["recording_error"] = str(e)
            print(f"\n⚠️  MCP recording error: {e}")

        state["last_update"] = time.time()

        return state

    def _finalize_node(self, state: OrchestrationState) -> OrchestrationState:
        """Finalize the workflow."""
        state["current_stage"] = WorkflowStage.COMPLETED

        # Calculate total time
        elapsed = time.time() - state.get("start_time", time.time())

        # Add completion message
        if state.get("error"):
            state["bot_response"] = f"❌ Error: {state['error']}"
        elif not state.get("bot_response"):
            state["bot_response"] = "Thank you for using our parking service!"

        # Print summary
        print(f"\n{'='*80}")
        print(f"Workflow completed in {elapsed:.2f}s")
        print(f"Stage: {state['current_stage'].value}")
        print(f"Conversation Type: {state['conversation_type'].value}")
        if state.get("reservation_id"):
            print(f"Reservation ID: {state['reservation_id']}")
        print(f"{'='*80}\n")

        return state

    def _handle_error_node(self, state: OrchestrationState) -> OrchestrationState:
        """Handle errors in the workflow."""
        state["current_stage"] = WorkflowStage.FAILED
        state["bot_response"] = f"❌ An error occurred: {state.get('error', 'Unknown error')}\n\nPlease try again or contact support."
        return state

    # ========================================================================
    # Routing Functions
    # ========================================================================

    def _route_after_classification(self, state: OrchestrationState) -> str:
        """Determine next step after classification."""
        conv_type = state.get("conversation_type")

        if conv_type == ConversationType.ADMIN_COMMAND:
            return "information"  # Admin commands are handled directly

        if conv_type == ConversationType.RESERVATION_REQUEST:
            return "reservation"

        return "information"

    def _route_after_data_collection(self, state: OrchestrationState) -> str:
        """Determine next step after data collection."""
        stage = state.get("current_stage")

        if stage == WorkflowStage.DATA_COLLECTION:
            return "collecting"
        elif stage == WorkflowStage.ADMIN_APPROVAL:
            return "escalate"
        else:
            return "error"

    def _route_after_admin_decision(self, state: OrchestrationState) -> str:
        """Determine next step after admin decision."""
        decision = state.get("admin_decision")

        if decision == "approved":
            return "approved"
        elif decision == "rejected":
            return "rejected"
        elif decision == "pending":
            return "pending"
        else:
            return "error"

    # ========================================================================
    # Public API
    # ========================================================================

    def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user message through the complete workflow.

        Args:
            user_input: User's message

        Returns:
            Dict with response and metadata
        """
        # Initialize state
        initial_state: OrchestrationState = {
            "current_stage": WorkflowStage.INITIALIZATION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": user_input,
            "user_messages": [],
            "bot_response": "",
            "reservation_data": {},
            "collection_step": 0,
            "reservation_id": None,
            "admin_decision": None,
            "admin_note": None,
            "recording_success": False,
            "recording_error": None,
            "start_time": time.time(),
            "last_update": time.time(),
            "error": None,
            "guardrail_violations": 0,
        }

        # Run workflow
        try:
            config = {"configurable": {"thread_id": "default"}}
            final_state = self.graph.invoke(initial_state, config)

            return {
                "success": True,
                "response": final_state.get("bot_response", ""),
                "stage": final_state.get("current_stage").value,
                "conversation_type": final_state.get("conversation_type").value,
                "reservation_id": final_state.get("reservation_id"),
                "elapsed_time": time.time() - final_state.get("start_time", time.time()),
                "state": final_state,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"An error occurred: {str(e)}",
            }

    def run_interactive_session(self):
        """Run an interactive session with the orchestrator."""
        print("\n" + "="*80)
        print("🚗 PARKING RESERVATION SYSTEM - LangGraph Orchestrator")
        print("="*80)
        print("Commands: 'quit' to exit, 'clear' to clear history")
        print("="*80 + "\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Goodbye!")
                    break

                if user_input.lower() == "clear":
                    self.rag_engine.clear_history()
                    print("✓ Conversation history cleared\n")
                    continue

                # Process message through workflow
                result = self.process_message(user_input)

                if result["success"]:
                    print(f"\nBot: {result['response']}\n")
                    print(f"[Stage: {result['stage']}, Time: {result['elapsed_time']:.2f}s]\n")
                else:
                    print(f"\nBot: {result['response']}\n")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")


def get_orchestrator() -> ParkingOrchestrator:
    """Get or create the global orchestrator instance."""
    return ParkingOrchestrator()
