"""Tests for RAG engine functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.core.rag_engine import (
    RAGEngine,
    MockRAGEngine,
    RAGResult,
    get_rag_engine,
    ConversationHistory,
)
from src.core.vector_store import InMemoryVectorStore
from src.core.llm_handler import LLMHandler


class TestConversationHistory:
    """Tests for ConversationHistory."""

    def test_add_message(self):
        """Test adding messages to history."""
        history = ConversationHistory(max_length=5)
        history.add_message("user", "Hello")
        history.add_message("assistant", "Hi there!")

        assert len(history.messages) == 2
        assert history.messages[0].role == "user"
        assert history.messages[0].content == "Hello"

    def test_history_trimming(self):
        """Test that history is trimmed to max_length."""
        history = ConversationHistory(max_length=3)
        for i in range(5):
            history.add_message("user", f"Message {i}")

        assert len(history.messages) == 3
        assert history.messages[0].content == "Message 2"

    def test_get_context(self):
        """Test getting context string."""
        history = ConversationHistory(max_length=10)
        history.add_message("user", "What are your hours?")
        history.add_message("assistant", "We're open 6 AM to 11 PM")

        context = history.get_context()
        assert "What are your hours?" in context
        assert "We're open 6 AM to 11 PM" in context

    def test_to_list(self):
        """Test converting to list format."""
        history = ConversationHistory(max_length=10)
        history.add_message("user", "Test message")

        message_list = history.to_list()
        assert isinstance(message_list, list)
        assert len(message_list) == 1
        assert message_list[0]["role"] == "user"

    def test_clear_history(self):
        """Test clearing history."""
        history = ConversationHistory(max_length=10)
        history.add_message("user", "Test")
        assert len(history.messages) == 1

        history.clear()
        assert len(history.messages) == 0


class TestRAGResult:
    """Tests for RAGResult dataclass."""

    def test_rag_result_creation(self):
        """Test creating RAGResult."""
        result = RAGResult(
            answer="Test answer",
            sources=[{"content": "Test source"}],
            retrieval_latency=0.1,
            generation_latency=0.5,
            total_latency=0.6,
        )

        assert result.answer == "Test answer"
        assert len(result.sources) == 1
        assert result.total_latency == 0.6


class TestMockRAGEngine:
    """Tests for MockRAGEngine."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock RAG engine."""
        return MockRAGEngine()

    def test_query_returns_result(self, mock_engine):
        """Test that query returns RAGResult."""
        result = mock_engine.query("What are your hours?")

        assert isinstance(result, RAGResult)
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    def test_query_hours_query(self, mock_engine):
        """Test querying about hours."""
        result = mock_engine.query("What are your working hours?")
        assert "hour" in result.answer.lower() or "open" in result.answer.lower()

    def test_query_price_query(self, mock_engine):
        """Test querying about prices."""
        result = mock_engine.query("How much does it cost?")
        assert "$" in result.answer or "rate" in result.answer.lower()

    def test_query_location_query(self, mock_engine):
        """Test querying about location."""
        result = mock_engine.query("Where are you located?")
        assert "123" in result.answer or "main street" in result.answer.lower()

    def test_query_reservation_query(self, mock_engine):
        """Test querying about reservations."""
        result = mock_engine.query("I want to make a reservation")
        assert "reservation" in result.answer.lower()

    def test_query_with_history(self, mock_engine):
        """Test that query uses conversation history."""
        mock_engine.query("Hello")
        mock_engine.query("What about prices?")

        assert len(mock_engine.conversation_history.messages) == 4  # 2 user + 2 assistant

    def test_clear_history(self, mock_engine):
        """Test clearing conversation history."""
        mock_engine.query("Test")
        assert len(mock_engine.conversation_history.messages) > 0

        mock_engine.clear_history()
        assert len(mock_engine.conversation_history.messages) == 0


class TestRAGEngine:
    """Tests for RAGEngine."""

    @pytest.fixture
    def vector_store(self):
        """Create a test vector store."""
        store = InMemoryVectorStore("test")
        store.create_collection(overwrite=True)
        store.add_documents([
            {"content": "Parking is $5 per hour", "metadata": {"section": "pricing"}},
            {"content": "Open from 6 AM to 11 PM", "metadata": {"section": "hours"}},
        ])
        return store

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM handler."""
        llm = Mock(spec=LLMHandler)
        llm.generate_response.return_value = "Test response"
        llm.get_embedding.return_value = [0.1] * 384
        return llm

    def test_engine_initialization(self, vector_store, mock_llm):
        """Test RAG engine initialization."""
        engine = RAGEngine(vector_store=vector_store, llm_handler=mock_llm)
        assert engine.vector_store == vector_store
        assert engine.llm_handler == mock_llm

    def test_query_with_sources(self, vector_store, mock_llm):
        """Test query returns sources."""
        mock_llm.generate_response.return_value = "Based on the information, parking is $5/hour"

        engine = RAGEngine(vector_store=vector_store, llm_handler=mock_llm)
        result = engine.query("How much is parking?")

        assert isinstance(result, RAGResult)
        assert len(result.sources) > 0
        assert result.retrieval_latency >= 0
        assert result.generation_latency >= 0

    def test_query_updates_history(self, vector_store, mock_llm):
        """Test that query updates conversation history."""
        engine = RAGEngine(vector_store=vector_store, llm_handler=mock_llm)
        engine.query("Test question")

        assert len(engine.conversation_history.messages) == 2  # User + Assistant

    def test_clear_history(self, vector_store, mock_llm):
        """Test clearing history."""
        engine = RAGEngine(vector_store=vector_store, llm_handler=mock_llm)
        engine.query("Test")
        assert len(engine.conversation_history.messages) > 0

        engine.clear_history()
        assert len(engine.conversation_history.messages) == 0


class TestRAGEngineIntegration:
    """Integration tests for RAG engine."""

    def test_end_to_end_query(self):
        """Test complete end-to-end query flow."""
        engine = get_rag_engine(use_mock=True)
        result = engine.query("What are your working hours?")

        assert result.answer
        assert isinstance(result.sources, list)
        assert result.total_latency >= 0

    def test_multiple_queries(self):
        """Test multiple sequential queries."""
        engine = get_rag_engine(use_mock=True)

        queries = [
            "What are your hours?",
            "How much does it cost?",
            "Where are you located?",
        ]

        for query in queries:
            result = engine.query(query)
            assert result.answer
            assert len(result.answer) > 0

    def test_conversation_context(self):
        """Test that conversation maintains context."""
        engine = get_rag_engine(use_mock=True)

        engine.query("What are your hours?")
        engine.query("And on weekends?")

        history = engine.get_history()
        assert len(history) >= 4  # At least 2 user + 2 assistant messages
