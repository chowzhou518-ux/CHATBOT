"""RAG Engine implementing Retrieval-Augmented Generation."""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.core.llm_handler import LLMHandler, ConversationHistory
from src.core.vector_store import VectorStore, get_vector_store
from src.config.settings import get_settings


@dataclass
class RAGResult:
    """Result from RAG query."""
    answer: str
    sources: List[Dict[str, Any]]
    retrieval_latency: float
    generation_latency: float
    total_latency: float


class RAGEngine:
    """Retrieval-Augmented Generation engine for parking information."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        llm_handler: Optional[LLMHandler] = None,
        system_prompt: Optional[str] = None,
        top_k: int = 3,
    ):
        """Initialize the RAG engine."""
        self.vector_store = vector_store or get_vector_store(use_in_memory=True)
        self.llm_handler = llm_handler or LLMHandler()
        self.top_k = top_k
        self.conversation_history = ConversationHistory(
            max_length=get_settings().max_context_length
        )

        # Default system prompt for parking assistant
        self.system_prompt = system_prompt or self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return """You are a helpful parking assistant for CityCenter Parking. Your role is to:

1. Provide accurate information about parking services, including:
   - Location and directions
   - Working hours
   - Pricing and rates
   - Available space types
   - Reservation process
   - Rules and regulations

2. Be friendly, professional, and concise in your responses.

3. If you don't know specific information about availability or pricing,
   suggest checking with the system for real-time data.

4. For reservation requests, collect the following information:
   - Customer's name and surname
   - License plate number
   - Preferred space type
   - Start and end time
   - Contact information (email or phone)

5. Never share sensitive customer information or other users' data.

6. If asked about topics unrelated to parking, politely redirect to parking-related questions.

Base your answers on the provided context, but speak naturally to the user."""

    def query(
        self,
        user_query: str,
        use_history: bool = True,
        include_sources: bool = False,
    ) -> RAGResult:
        """
        Process a user query using RAG.

        Args:
            user_query: The user's question
            use_history: Whether to include conversation history
            include_sources: Whether to include source references

        Returns:
            RAGResult with answer and metadata.
        """
        start_time = time.time()

        # Add user query to history
        self.conversation_history.add_message("user", user_query)

        # Retrieve relevant documents
        retrieval_start = time.time()
        sources = self.vector_store.search(
            query=user_query,
            top_k=self.top_k,
        )
        retrieval_latency = time.time() - retrieval_start

        # Build context from retrieved documents
        context = self._build_context(sources)

        # Get conversation context if enabled
        conversation_context = ""
        if use_history:
            conversation_context = self.conversation_history.get_context()

        # Generate response
        generation_start = time.time()

        # Build enhanced prompt with context
        enhanced_prompt = self._build_prompt(user_query, context)

        answer = self.llm_handler.generate_response(
            prompt=enhanced_prompt,
            system_prompt=self.system_prompt,
            context=conversation_context if use_history else None,
        )

        generation_latency = time.time() - generation_start

        # Add assistant response to history
        self.conversation_history.add_message("assistant", answer)

        # Add source references if requested
        if include_sources and sources:
            source_refs = self._format_sources(sources)
            answer = f"{answer}\n\nSources:\n{source_refs}"

        total_latency = time.time() - start_time

        return RAGResult(
            answer=answer,
            sources=sources,
            retrieval_latency=retrieval_latency,
            generation_latency=generation_latency,
            total_latency=total_latency,
        )

    def _build_context(self, sources: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved sources."""
        if not sources:
            return "No specific information found in the knowledge base."

        context_parts = []
        for i, source in enumerate(sources, 1):
            content = source.get("content", "")
            context_parts.append(f"[Source {i}] {content}")

        return "\n\n".join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build the enhanced prompt with context."""
        return f"""Relevant Information:
{context}

User Question: {query}

Please provide a helpful answer based on the information above."""

    def _format_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Format sources for display."""
        formatted = []
        for i, source in enumerate(sources, 1):
            metadata = source.get("metadata", "{}")
            score = source.get("score", 0.0)
            formatted.append(f"- Source {i}: {metadata} (relevance: {score:.2f})")
        return "\n".join(formatted)

    def query_with_tools(
        self,
        user_query: str,
        tools: List[Dict[str, Any]],
    ) -> Any:
        """
        Query using Claude's tool use capabilities.

        Args:
            user_query: The user's question
            tools: List of available tools

        Returns:
            Response that may include tool calls.
        """
        # Build messages
        messages = [{"role": "user", "content": user_query}]

        return self.llm_handler.generate_with_tools(
            messages=messages,
            tools=tools,
            system_prompt=self.system_prompt,
        )

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.to_list()

    def set_system_prompt(self, prompt: str) -> None:
        """Update the system prompt."""
        self.system_prompt = prompt

    def evaluate_retrieval(
        self,
        query: str,
        expected_sources: List[str],
    ) -> Dict[str, Any]:
        """
        Evaluate retrieval quality for a query.

        Args:
            query: The test query
            expected_sources: Expected document sections

        Returns:
            Evaluation metrics.
        """
        sources = self.vector_store.search(query=query, top_k=5)

        found_sections = set()
        for source in sources:
            metadata = source.get("metadata", "{}")
            for expected in expected_sources:
                if expected.lower() in metadata.lower():
                    found_sections.add(expected)

        return {
            "query": query,
            "expected": expected_sources,
            "found": list(found_sections),
            "recall": len(found_sections) / len(expected_sources) if expected_sources else 0,
            "num_results": len(sources),
        }


class MockRAGEngine(RAGEngine):
    """Mock RAG engine for testing without actual services."""

    def __init__(self):
        """Initialize mock engine."""
        # Don't call super().__init__() to avoid actual connections
        self.conversation_history = ConversationHistory(max_length=10)
        self.system_prompt = self._get_default_system_prompt()
        self.top_k = 3

        # Mock responses
        self.mock_responses = {
            "hours": "Our working hours are Monday-Friday: 6 AM - 11 PM, Saturday: 7 AM - 12 AM, Sunday: 8 AM - 10 PM.",
            "price": "Our rates start at $1.50/hour for motorcycles, $2.50/hour for compact spaces, and $3.00/hour for standard spaces.",
            "location": "We are located at 123 Main Street, Downtown Metropolitan City, CA 90210.",
            "reservation": "To make a reservation, I'll need your name, license plate number, preferred space type, and start/end times.",
            "default": "I'd be happy to help you with information about our parking services. What would you like to know?",
        }

    def query(self, user_query: str, use_history: bool = True, include_sources: bool = False) -> RAGResult:
        """Mock query implementation."""
        start_time = time.time()

        # Simple keyword matching
        query_lower = user_query.lower()
        answer = self.mock_responses["default"]

        if "hour" in query_lower or "open" in query_lower or "close" in query_lower:
            answer = self.mock_responses["hours"]
        elif "price" in query_lower or "rate" in query_lower or "cost" in query_lower or "much" in query_lower:
            answer = self.mock_responses["price"]
        elif "where" in query_lower or "location" in query_lower or "address" in query_lower:
            answer = self.mock_responses["location"]
        elif "reservation" in query_lower or "book" in query_lower:
            answer = self.mock_responses["reservation"]

        self.conversation_history.add_message("user", user_query)
        self.conversation_history.add_message("assistant", answer)

        return RAGResult(
            answer=answer,
            sources=[{"content": "Mock source", "metadata": "mock", "score": 1.0}],
            retrieval_latency=0.01,
            generation_latency=0.05,
            total_latency=time.time() - start_time,
        )


def get_rag_engine(use_mock: bool = False) -> RAGEngine:
    """Get RAG engine instance."""
    if use_mock:
        return MockRAGEngine()
    return RAGEngine()


def initialize_rag_engine() -> RAGEngine:
    """Initialize RAG engine with vector store."""
    from src.core.vector_store import initialize_vector_store

    # Initialize vector store
    initialize_vector_store()

    # Create and return RAG engine
    return get_rag_engine(use_mock=True)  # Use mock for demo reliability
