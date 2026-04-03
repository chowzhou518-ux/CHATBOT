"""Tests for the LangGraph orchestration system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.orchestration.graph import (
    ParkingOrchestrator,
    WorkflowStage,
    ConversationType,
    OrchestrationState,
)


class TestOrchestrationState:
    """Test OrchestrationState."""

    def test_state_creation(self):
        """Test creating a state."""
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
            "start_time": 1234567890.0,
            "last_update": 1234567890.0,
            "error": None,
            "guardrail_violations": 0,
        }

        assert state["current_stage"] == WorkflowStage.INITIALIZATION
        assert state["conversation_type"] == ConversationType.INFORMATION_QUERY
        assert state["user_input"] == "Hello"


class TestParkingOrchestrator:
    """Test ParkingOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator for testing."""
        return ParkingOrchestrator()

    def test_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator is not None
        assert orchestrator.graph is not None
        assert orchestrator.rag_engine is not None
        assert orchestrator.parking_tools is not None
        assert orchestrator.guardrails is not None

    def test_process_information_query(self, orchestrator):
        """Test processing an information query."""
        result = orchestrator.process_message("What are your working hours?")

        assert result["success"] is True
        assert "response" in result
        assert len(result["response"]) > 0
        assert result["conversation_type"] == "information_query"
        assert "stage" in result

    def test_process_reservation_request(self, orchestrator):
        """Test processing a reservation request."""
        result = orchestrator.process_message("I want to make a reservation")

        assert result["success"] is True
        assert "response" in result
        assert result["conversation_type"] == "reservation_request"

    def test_classify_admin_command(self, orchestrator):
        """Test classifying admin commands."""
        result = orchestrator.process_message("list")

        # Should handle admin commands
        assert result["success"] is True

    def test_guardrail_integration(self, orchestrator):
        """Test that guardrails are integrated."""
        # Test with potentially sensitive input
        result = orchestrator.process_message("My SSN is 123-45-6789")

        assert result["success"] is True
        # Response should not contain the SSN
        assert "123-45-6789" not in result.get("response", "")

    def test_elapsed_time_tracking(self, orchestrator):
        """Test that elapsed time is tracked."""
        result = orchestrator.process_message("Hello")

        assert "elapsed_time" in result
        assert result["elapsed_time"] >= 0
        assert result["elapsed_time"] < 10  # Should be fast

    def test_state_transitions(self, orchestrator):
        """Test state transitions through workflow."""
        # Information query should complete
        result = orchestrator.process_message("Where are you located?")
        state = result.get("state")

        if state:
            assert state["current_stage"] == WorkflowStage.COMPLETED
            assert len(state["user_messages"]) >= 2  # At least user + bot


class TestWorkflowStages:
    """Test workflow stages."""

    def test_initialization_stage(self):
        """Test initialization stage."""
        assert WorkflowStage.INITIALIZATION == "initialization"
        assert WorkflowStage.USER_INTERACTION == "user_interaction"
        assert WorkflowStage.DATA_COLLECTION == "data_collection"
        assert WorkflowStage.ADMIN_APPROVAL == "admin_approval"
        assert WorkflowStage.RECORDING == "recording"
        assert WorkflowStage.COMPLETED == "completed"
        assert WorkflowStage.FAILED == "failed"

    def test_conversation_types(self):
        """Test conversation types."""
        assert ConversationType.INFORMATION_QUERY == "information_query"
        assert ConversationType.RESERVATION_REQUEST == "reservation_request"
        assert ConversationType.STATUS_CHECK == "status_check"
        assert ConversationType.ADMIN_COMMAND == "admin_command"


class TestOrchestratorIntegration:
    """Integration tests for the orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator for testing."""
        return ParkingOrchestrator()

    def test_complete_information_flow(self, orchestrator):
        """Test complete information query flow."""
        result = orchestrator.process_message(
            "What are your parking rates for compact spaces?"
        )

        assert result["success"] is True
        assert result["stage"] == "completed"
        assert result["conversation_type"] == "information_query"
        assert result["elapsed_time"] < 5.0  # Should respond quickly

    def test_error_handling(self, orchestrator):
        """Test error handling in orchestrator."""
        # Test with empty input
        result = orchestrator.process_message("")

        # Should handle gracefully
        assert result["success"] is True

    def test_multiple_queries(self, orchestrator):
        """Test processing multiple queries in sequence."""
        queries = [
            "What are your hours?",
            "How much does it cost?",
            "Where are you located?",
        ]

        for query in queries:
            result = orchestrator.process_message(query)
            assert result["success"] is True
            assert len(result["response"]) > 0

    @pytest.mark.slow
    def test_conversation_history(self, orchestrator):
        """Test that conversation history is maintained."""
        # First query
        result1 = orchestrator.process_message("What are your hours?")
        state1 = result1.get("state")

        # Second query (should have context)
        result2 = orchestrator.process_message("What about weekends?")
        state2 = result2.get("state")

        if state1 and state2:
            # Second state should have more messages
            assert len(state2["user_messages"]) >= len(state1["user_messages"])


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

    def test_handle_information_query_node(self, orchestrator):
        """Test the information query handler."""
        state: OrchestrationState = {
            "current_stage": WorkflowStage.USER_INTERACTION,
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

        result = orchestrator._handle_information_query_node(state)

        assert result["current_stage"] == WorkflowStage.COMPLETED
        assert len(result["bot_response"]) > 0
        assert len(result["user_messages"]) >= 2


# Import time for node tests
import time
