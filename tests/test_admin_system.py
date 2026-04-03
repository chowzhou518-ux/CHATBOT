"""Tests for the administrator system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.data.reservation_state import (
    ReservationRequest,
    ReservationStatus,
    CommunicationChannel,
)
from src.data.reservation_manager import ReservationManager
from src.chatbot.admin_agent import AdminAgent
from src.chatbot.escalation import EscalationManager, UserFacingEscalationService
from src.chatbot.channels import MockChannelHandler, EmailChannelHandler


class TestReservationRequest:
    """Test ReservationRequest dataclass."""

    def test_create_reservation_request(self):
        """Test creating a reservation request."""
        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        assert request.reservation_id == "test-123"
        assert request.user_name == "John"
        assert request.user_surname == "Doe"
        assert request.status == ReservationStatus.PENDING
        assert request.communication_channel == CommunicationChannel.EMAIL

    def test_to_dict(self):
        """Test converting reservation to dictionary."""
        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        data = request.to_dict()

        assert data["reservation_id"] == "test-123"
        assert data["user_name"] == "John"
        assert data["status"] == "pending"
        assert "start_time" in data
        assert "end_time" in data

    def test_from_dict(self):
        """Test creating reservation from dictionary."""
        data = {
            "reservation_id": "test-123",
            "user_name": "John",
            "user_surname": "Doe",
            "car_number": "ABC-123",
            "start_time": "2026-04-10T10:00:00",
            "end_time": "2026-04-10T12:00:00",
            "space_type": "standard",
            "contact_info": "john@example.com",
            "status": "pending",
            "created_at": "2026-04-10T09:00:00",
            "updated_at": "2026-04-10T09:00:00",
        }

        request = ReservationRequest.from_dict(data)

        assert request.reservation_id == "test-123"
        assert request.user_name == "John"
        assert request.status == ReservationStatus.PENDING

    def test_is_expired(self):
        """Test expiration check."""
        # Non-expired request
        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
            expiration_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert not request.is_expired()

        # Expired request
        request.expiration_time = datetime.utcnow() - timedelta(hours=1)
        assert request.is_expired()

    def test_can_be_approved(self):
        """Test if reservation can be approved."""
        # Can be approved
        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
            expiration_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert request.can_be_approved()

        # Cannot be approved (already rejected)
        request.status = ReservationStatus.REJECTED
        assert not request.can_be_approved()

        # Cannot be approved (expired)
        request.status = ReservationStatus.PENDING
        request.expiration_time = datetime.utcnow() - timedelta(hours=1)
        assert not request.can_be_approved()


class TestReservationManager:
    """Test ReservationManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a temporary reservation manager."""
        db_url = f"sqlite:///{tmp_path}/test.db"
        manager = ReservationManager(database_url=db_url)
        yield manager
        manager.close()

    def test_create_reservation_request(self, manager):
        """Test creating a reservation request."""
        request = manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        assert request.user_name == "John"
        assert request.user_surname == "Doe"
        assert request.status == ReservationStatus.PENDING
        assert request.reservation_id is not None

    def test_get_reservation(self, manager):
        """Test retrieving a reservation."""
        # Create a reservation
        created = manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Get the reservation
        retrieved = manager.get_reservation(created.reservation_id)

        assert retrieved is not None
        assert retrieved.reservation_id == created.reservation_id
        assert retrieved.user_name == "John"

    def test_approve_reservation(self, manager):
        """Test approving a reservation."""
        # Create a reservation
        created = manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Approve it
        approved = manager.approve_reservation(
            created.reservation_id,
            admin_note="Looks good!",
        )

        assert approved is not None
        assert approved.status == ReservationStatus.APPROVED
        assert approved.admin_note == "Looks good!"

    def test_reject_reservation(self, manager):
        """Test rejecting a reservation."""
        # Create a reservation
        created = manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Reject it
        rejected = manager.reject_reservation(
            created.reservation_id,
            admin_note="Space not available",
        )

        assert rejected is not None
        assert rejected.status == ReservationStatus.REJECTED
        assert rejected.admin_note == "Space not available"

    def test_get_pending_reservations(self, manager):
        """Test getting pending reservations."""
        # Create multiple reservations
        manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        manager.create_reservation_request(
            user_name="Jane",
            user_surname="Smith",
            car_number="XYZ-789",
            start_time=datetime(2026, 4, 11, 10, 0),
            end_time=datetime(2026, 4, 11, 12, 0),
            space_type="compact",
            contact_info="jane@example.com",
        )

        pending = manager.get_pending_reservations()

        assert len(pending) == 2
        assert all(r.status == ReservationStatus.PENDING for r in pending)

    def test_get_statistics(self, manager):
        """Test getting statistics."""
        # Create reservations with different states
        r1 = manager.create_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        manager.approve_reservation(r1.reservation_id)

        stats = manager.get_statistics()

        assert stats["total"] == 1
        assert stats["approved"] == 1
        assert stats["pending"] == 0


class TestAdminAgent:
    """Test AdminAgent."""

    @pytest.fixture
    def agent(self):
        """Create an admin agent."""
        return AdminAgent()

    def test_list_pending_reservations(self, agent):
        """Test listing pending reservations tool."""
        # This would require mocking the reservation manager
        # For now, just test that the tool exists
        assert len(agent.tools) > 0
        assert any(tool.name == "list_pending_reservations" for tool in agent.tools)

    def test_parse_admin_response(self, agent):
        """Test parsing admin responses."""
        # Test approve
        result = agent.parse_admin_response("APPROVE test-123 Approved for weekend")
        assert result["action"] == "approve"
        assert result["reservation_id"] == "test-123"
        assert result["note"] == "Approved for weekend"

        # Test reject
        result = agent.parse_admin_response("REJECT test-123 Space already booked")
        assert result["action"] == "reject"
        assert result["reservation_id"] == "test-123"
        assert result["reason"] == "Space already booked"

        # Test invalid
        result = agent.parse_admin_response("INVALID COMMAND")
        assert result["action"] == "unknown"

    def test_process_message_list(self, agent):
        """Test processing list command."""
        response = agent.process_message("list")
        # Should return a response (even if no reservations)
        assert response is not None
        assert isinstance(response, str)

    def test_process_message_stats(self, agent):
        """Test processing stats command."""
        response = agent.process_message("stats")
        assert response is not None
        assert isinstance(response, str)


class TestEscalationManager:
    """Test EscalationManager."""

    @pytest.fixture
    def escalation_manager(self, tmp_path):
        """Create an escalation manager with temp database."""
        db_url = f"sqlite:///{tmp_path}/test.db"
        return EscalationManager(default_channel=CommunicationChannel.EMAIL)

    def test_escalate_reservation(self, escalation_manager):
        """Test escalating a reservation."""
        result = escalation_manager.escalate_reservation(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        assert result["success"] is True
        assert "reservation_id" in result
        assert result["status"] == "pending"

    def test_check_reservation_status(self, escalation_manager):
        """Test checking reservation status."""
        # First create a reservation
        escalate_result = escalation_manager.escalate_reservation(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Check status
        status_result = escalation_manager.check_reservation_status(
            escalate_result["reservation_id"]
        )

        assert status_result["success"] is True
        assert status_result["status"] == "pending"

    def test_get_pending_reservations(self, escalation_manager):
        """Test getting pending reservations."""
        # Create a reservation
        escalation_manager.escalate_reservation(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Get pending
        pending = escalation_manager.get_pending_reservations()

        assert len(pending) >= 1
        assert all(r["status"] == "pending" for r in pending)


class TestUserFacingEscalationService:
    """Test UserFacingEscalationService."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a user-facing escalation service."""
        db_url = f"sqlite:///{tmp_path}/test.db"
        manager = EscalationManager(default_channel=CommunicationChannel.EMAIL)
        return UserFacingEscalationService(escalation_manager=manager)

    def test_submit_reservation_request(self, service):
        """Test submitting a reservation request."""
        response = service.submit_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        assert "Request ID" in response
        assert "Pending Administrator Approval" in response
        assert "✅" in response

    def test_check_status(self, service):
        """Test checking reservation status."""
        # First submit a request
        submit_response = service.submit_reservation_request(
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        # Extract reservation ID from response
        import re
        match = re.search(r'Request ID: ([a-f0-9-]+)', submit_response)
        assert match is not None

        reservation_id = match.group(1)

        # Check status
        status_response = service.check_status(reservation_id)

        assert "pending" in status_response.lower()
        assert "⏳" in status_response


class TestChannelHandlers:
    """Test communication channel handlers."""

    def test_mock_channel_handler(self):
        """Test MockChannelHandler."""
        handler = MockChannelHandler()

        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        result = handler.send_request(request, "admin@example.com")

        assert result["success"] is True
        assert "message_id" in result
        assert result["channel"] == "mock"

    def test_mock_channel_stores_messages(self):
        """Test that MockChannelHandler stores sent messages."""
        handler = MockChannelHandler()

        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        handler.send_request(request, "admin@example.com")

        assert len(handler.sent_messages) == 1
        assert handler.sent_messages[0]["reservation"]["reservation_id"] == "test-123"

    def test_format_request_message(self):
        """Test formatting request message."""
        handler = MockChannelHandler()

        request = ReservationRequest(
            reservation_id="test-123",
            user_name="John",
            user_surname="Doe",
            car_number="ABC-123",
            start_time=datetime(2026, 4, 10, 10, 0),
            end_time=datetime(2026, 4, 10, 12, 0),
            space_type="standard",
            contact_info="john@example.com",
        )

        message = handler.format_request_message(request)

        assert "test-123" in message
        assert "John Doe" in message
        assert "ABC-123" in message
        assert "APPROVE" in message
        assert "REJECT" in message
