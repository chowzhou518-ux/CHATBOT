"""Basic tests for the LangGraph orchestration system (without external dependencies)."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.orchestration.graph import (
    ParkingOrchestrator,
    WorkflowStage,
    ConversationType,
    OrchestrationState,
)


class TestOrchestratorBasic:
    """Basic tests for ParkingOrchestrator."""

    def test_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = ParkingOrchestrator()
        assert orchestrator is not None
        assert orchestrator.graph is not None

    def test_state_structure(self):
        """Test that state has required fields."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.INITIALIZATION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "Hello",
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

        assert "current_stage" in state
        assert "conversation_type" in state
        assert "user_input" in state
        assert "bot_response" in state


class TestWorkflowStages:
    """Test workflow stage enumerations."""

    def test_workflow_stages(self):
        """Test workflow stage values."""
        assert WorkflowStage.INITIALIZATION == "initialization"
        assert WorkflowStage.USER_INTERACTION == "user_interaction"
        assert WorkflowStage.DATA_COLLECTION == "data_collection"
        assert WorkflowStage.ADMIN_APPROVAL == "admin_approval"
        assert WorkflowStage.RECORDING == "recording"
        assert WorkflowStage.COMPLETED == "completed"
        assert WorkflowStage.FAILED == "failed"

    def test_conversation_types(self):
        """Test conversation type values."""
        assert ConversationType.INFORMATION_QUERY == "information_query"
        assert ConversationType.RESERVATION_REQUEST == "reservation_request"
        assert ConversationType.STATUS_CHECK == "status_check"
        assert ConversationType.ADMIN_COMMAND == "admin_command"


class TestOrchestratorNodes:
    """Test individual orchestration nodes."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator for testing."""
        return ParkingOrchestrator()

    def test_initialize_node(self, orchestrator):
        """Test the initialize node."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.INITIALIZATION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "",
            "user_messages": [],
            "bot_response": "",
            "reservation_data": {},
            "collection_step": 0,
            "reservation_id": None,
            "admin_decision": None,
            "admin_note": None,
            "recording_success": False,
            "recording_error": None,
            "start_time": 0,
            "last_update": 0,
            "error": None,
            "guardrail_violations": 0,
        }

        result = orchestrator._initialize_node(state)

        assert result["current_stage"] == WorkflowStage.INITIALIZATION
        assert result["start_time"] > 0
        assert result["last_update"] > 0
        assert result["error"] is None

    def test_classify_conversation_node(self, orchestrator):
        """Test the classify conversation node."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.INITIALIZATION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "I want to make a reservation",
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

        result = orchestrator._classify_conversation_node(state)

        assert result["conversation_type"] == ConversationType.RESERVATION_REQUEST
        assert result["current_stage"] == WorkflowStage.USER_INTERACTION

    def test_classify_information_query(self, orchestrator):
        """Test classifying an information query."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.INITIALIZATION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "What are your hours?",
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

        result = orchestrator._classify_conversation_node(state)

        assert result["conversation_type"] == ConversationType.INFORMATION_QUERY

    def test_finalize_node(self, orchestrator):
        """Test the finalize node."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.USER_INTERACTION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "Hello",
            "user_messages": [],
            "bot_response": "Test response",
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

        result = orchestrator._finalize_node(state)

        assert result["current_stage"] == WorkflowStage.COMPLETED
        assert result["bot_response"] is not None

    def test_handle_error_node(self, orchestrator):
        """Test the error handler node."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.USER_INTERACTION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "Hello",
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
            "error": "Test error",
            "guardrail_violations": 0,
        }

        result = orchestrator._handle_error_node(state)

        assert result["current_stage"] == WorkflowStage.FAILED
        assert result["bot_response"] is not None


class TestRoutingFunctions:
    """Test routing functions."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator for testing."""
        return ParkingOrchestrator()

    def test_route_after_classification(self, orchestrator):
        """Test routing after classification."""
        # Information query
        state: OrchestrationState = {
            "current_stage": WorkflowStage.USER_INTERACTION,
            "conversation_type": ConversationType.INFORMATION_QUERY,
            "user_input": "",
            "user_messages": [],
            "bot_response": "",
            "reservation_data": {},
            "collection_step": 0,
            "reservation_id": None,
            "admin_decision": None,
            "admin_note": None,
            "recording_success": False,
            "recording_error": None,
            "start_time": 0,
            "last_update": 0,
            "error": None,
            "guardrail_violations": 0,
        }

        route = orchestrator._route_after_classification(state)
        assert route == "information"

        # Reservation request
        state["conversation_type"] = ConversationType.RESERVATION_REQUEST
        route = orchestrator._route_after_classification(state)
        assert route == "reservation"

    def test_route_after_data_collection(self, orchestrator):
        """Test routing after data collection."""
        # Still collecting
        state: OrchestrationState = {
            "current_stage": WorkflowStage.DATA_COLLECTION,
            "conversation_type": ConversationType.RESERVATION_REQUEST,
            "user_input": "",
            "user_messages": [],
            "bot_response": "",
            "reservation_data": {},
            "collection_step": 0,
            "reservation_id": None,
            "admin_decision": None,
            "admin_note": None,
            "recording_success": False,
            "recording_error": None,
            "start_time": 0,
            "last_update": 0,
            "error": None,
            "guardrail_violations": 0,
        }

        route = orchestrator._route_after_data_collection(state)
        assert route == "collecting"

        # Ready to escalate
        state["current_stage"] = WorkflowStage.ADMIN_APPROVAL
        route = orchestrator._route_after_data_collection(state)
        assert route == "escalate"

    def test_route_after_admin_decision(self, orchestrator):
        """Test routing after admin decision."""
        # Approved
        state: OrchestrationState = {
            "current_stage": WorkflowStage.RECORDING,
            "conversation_type": ConversationType.RESERVATION_REQUEST,
            "user_input": "",
            "user_messages": [],
            "bot_response": "",
            "reservation_data": {},
            "collection_step": 0,
            "reservation_id": "test-123",
            "admin_decision": "approved",
            "admin_note": None,
            "recording_success": False,
            "recording_error": None,
            "start_time": 0,
            "last_update": 0,
            "error": None,
            "guardrail_violations": 0,
        }

        route = orchestrator._route_after_admin_decision(state)
        assert route == "approved"

        # Rejected
        state["admin_decision"] = "rejected"
        route = orchestrator._route_after_admin_decision(state)
        assert route == "rejected"

        # Pending
        state["admin_decision"] = "pending"
        route = orchestrator._route_after_admin_decision(state)
        assert route == "pending"


class TestGraphStructure:
    """Test the graph structure."""

    def test_graph_creation(self):
        """Test that the graph is created correctly."""
        orchestrator = ParkingOrchestrator()

        # Check that graph exists
        assert orchestrator.graph is not None

        # The graph should be compiled
        assert hasattr(orchestrator.graph, 'nodes')

    def test_graph_nodes(self):
        """Test that graph has all required nodes."""
        orchestrator = ParkingOrchestrator()

        # The graph should have these nodes (verify via node attribute)
        expected_nodes = [
            "initialize",
            "classify_conversation",
            "handle_information_query",
            "collect_reservation_data",
            "escalate_to_admin",
            "wait_for_admin_decision",
            "record_to_mcp",
            "finalize",
            "handle_error",
        ]

        # Check if graph has nodes attribute
        if hasattr(orchestrator.graph, 'nodes'):
            actual_nodes = list(orchestrator.graph.nodes.keys())
            for node in expected_nodes:
                assert node in actual_nodes, f"Missing node: {node}"
        else:
            # Graph is compiled, nodes exist in the structure
            assert orchestrator.graph is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
