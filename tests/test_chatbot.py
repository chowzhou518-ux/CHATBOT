"""Tests for chatbot agent functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.chatbot.tools import (
    ParkingTools,
    ReservationDataCollector,
    get_parking_tools,
)
from src.chatbot.agent import (
    SimpleParkingChatbot,
    get_simple_chatbot,
    Intent,
)


class TestParkingTools:
    """Tests for ParkingTools."""

    @pytest.fixture
    def tools(self):
        """Create parking tools instance."""
        return ParkingTools()

    def test_get_parking_info(self, tools):
        """Test getting parking information."""
        info = tools.get_parking_info("location")
        assert info  # Should return some content
        assert isinstance(info, str)

    def test_check_availability_default(self, tools):
        """Test checking availability for default space type."""
        avail = tools.check_availability("standard")
        assert avail  # Should return some content
        assert isinstance(avail, str)

    def test_get_all_availability(self, tools):
        """Test getting all availability info."""
        avail = tools.get_all_availability()
        assert avail  # Should return some content
        assert isinstance(avail, str)

    def test_get_prices(self, tools):
        """Test getting pricing information."""
        prices = tools.get_prices()
        assert prices  # Should return pricing info
        assert "$" in prices or "rate" in prices.lower()

    def test_get_prices_for_type(self, tools):
        """Test getting pricing for specific space type."""
        prices = tools.get_prices("compact")
        assert prices  # Should return pricing info
        assert isinstance(prices, str)

    def test_get_location_info(self, tools):
        """Test getting location information."""
        location = tools.get_location_info()
        assert location  # Should return location info
        assert "123" in location or "street" in location.lower()

    def test_get_working_hours(self, tools):
        """Test getting working hours."""
        hours = tools.get_working_hours()
        assert hours  # Should return hours
        assert "hour" in hours.lower() or "open" in hours.lower()

    def test_get_payment_methods(self, tools):
        """Test getting payment methods."""
        methods = tools.get_payment_methods()
        assert methods  # Should return payment info
        assert isinstance(methods, str)

    def test_get_rules_summary(self, tools):
        """Test getting rules summary."""
        rules = tools.get_rules_summary()
        assert rules  # Should return rules
        assert isinstance(rules, str)


class TestReservationDataCollector:
    """Tests for reservation data collection."""

    @pytest.fixture
    def collector(self):
        """Create a fresh collector for each test."""
        return ReservationDataCollector()

    def test_initial_state(self, collector):
        """Test initial collector state."""
        assert collector.current_step == 0
        assert collector.collected_data["name"] is None

    def test_get_first_prompt(self, collector):
        """Test getting first collection prompt."""
        prompt = collector.get_current_prompt()
        assert prompt  # Should have a prompt
        assert "name" in prompt.lower()

    def test_collect_name(self, collector):
        """Test collecting name."""
        result = collector.process_input("John")
        assert result["status"] == "collecting"
        assert collector.collected_data["name"] == "John"

    def test_collect_surname(self, collector):
        """Test collecting surname."""
        collector.collected_data["name"] = "John"
        collector.current_step = 1

        result = collector.process_input("Smith")
        assert result["status"] == "collecting"
        assert collector.collected_data["surname"] == "Smith"

    def test_collect_car_number(self, collector):
        """Test collecting car number."""
        # Advance to car number step
        for i in range(2):
            collector.current_step += 1

        result = collector.process_input("ABC-1234")
        assert result["status"] == "collecting"
        assert collector.collected_data["car_number"] == "ABC-1234"

    def test_invalid_name_too_short(self, collector):
        """Test validation for name that's too short."""
        result = collector.process_input("J")
        assert result["status"] == "error"
        assert "too short" in result["error"].lower()

    def test_invalid_space_type(self, collector):
        """Test validation for invalid space type."""
        # Advance to space type step
        for i in range(3):
            collector.current_step += 1

        result = collector.process_input("spaceship")
        assert result["status"] == "error"
        assert "invalid" in result["error"].lower()

    def test_valid_space_type(self, collector):
        """Test valid space type."""
        # Advance to space type step
        for i in range(3):
            collector.current_step += 1

        result = collector.process_input("standard")
        assert result["status"] == "collecting"
        assert collector.collected_data["space_type"] == "standard"

    def test_reset(self, collector):
        """Test resetting collector."""
        collector.collected_data["name"] = "Test"
        collector.current_step = 5

        collector.reset()
        assert collector.current_step == 0
        assert collector.collected_data["name"] is None


class TestSimpleParkingChatbot:
    """Tests for SimpleParkingChatbot."""

    @pytest.fixture
    def chatbot(self):
        """Create a chatbot instance."""
        return SimpleParkingChatbot()

    def test_initial_state(self, chatbot):
        """Test initial chatbot state."""
        assert chatbot.in_reservation_mode is False
        assert chatbot.reservation_collector is not None

    def test_chat_hours_query(self, chatbot):
        """Test chatting about hours."""
        response = chatbot.chat("What are your hours?")
        assert response  # Should have a response
        assert len(response) > 0

    def test_chat_price_query(self, chatbot):
        """Test chatting about prices."""
        response = chatbot.chat("How much does it cost?")
        assert response
        assert "$" in response or "rate" in response.lower()

    def test_chat_location_query(self, chatbot):
        """Test chatting about location."""
        response = chatbot.chat("Where are you located?")
        assert response
        assert "123" in response or "street" in response.lower()

    def test_chat_availability_query(self, chatbot):
        """Test chatting about availability."""
        response = chatbot.chat("Do you have any spaces available?")
        assert response
        assert "available" in response.lower()

    def test_chat_payment_query(self, chatbot):
        """Test chatting about payment."""
        response = chatbot.chat("What payment methods do you accept?")
        assert response
        assert "payment" in response.lower()

    def test_start_reservation(self, chatbot):
        """Test starting a reservation."""
        response = chatbot.chat("I want to make a reservation")
        assert response
        assert chatbot.in_reservation_mode is True

    def test_cancel_reservation(self, chatbot):
        """Test canceling reservation flow."""
        # Start reservation
        chatbot.chat("I want to book")
        assert chatbot.in_reservation_mode is True

        # Cancel
        response = chatbot.chat("cancel this")
        assert chatbot.in_reservation_mode is False

    def test_guardrail_processing(self, chatbot):
        """Test that guardrails process input."""
        # Clean input should pass through
        response = chatbot.chat("What are your hours?")
        assert response  # Should get a response


class TestChatbotIntegration:
    """Integration tests for chatbot."""

    def test_multi_turn_conversation(self):
        """Test multi-turn conversation."""
        chatbot = get_simple_chatbot()

        # First query
        response1 = chatbot.chat("What are your hours?")
        assert response1

        # Second query (context maintained)
        response2 = chatbot.chat("And on weekends?")
        assert response2

    def test_information_then_reservation(self):
        """Test flow from information to reservation."""
        chatbot = get_simple_chatbot()

        # Ask for info
        response1 = chatbot.chat("What are your rates?")
        assert response1
        assert not chatbot.in_reservation_mode

        # Start reservation
        response2 = chatbot.chat("I'd like to make a reservation")
        assert response2
        assert chatbot.in_reservation_mode is True

    def test_various_topics(self):
        """Test handling various parking topics."""
        chatbot = get_simple_chatbot()

        topics = [
            "Where are you located?",
            "What are your working hours?",
            "How much is parking?",
            "Do you have EV charging?",
            "What payment methods do you accept?",
        ]

        for topic in topics:
            response = chatbot.chat(topic)
            assert response, f"No response for: {topic}"
            assert len(response) > 0

    def test_graceful_unknown_queries(self):
        """Test handling of unknown queries."""
        chatbot = get_simple_chatbot()

        # Query about unrelated topic
        response = chatbot.chat("What's the weather like?")
        assert response  # Should still respond
        assert isinstance(response, str)
