"""Tests for vector store functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.core.vector_store import (
    VectorStore,
    InMemoryVectorStore,
    get_vector_store,
)


class TestInMemoryVectorStore:
    """Tests for InMemoryVectorStore."""

    @pytest.fixture
    def vector_store(self):
        """Create a fresh vector store for each test."""
        store = InMemoryVectorStore("test_collection")
        store.create_collection(overwrite=True)
        return store

    def test_create_collection(self, vector_store):
        """Test collection creation."""
        vector_store.create_collection(overwrite=True)
        assert vector_store.documents == []

    def test_add_documents(self, vector_store):
        """Test adding documents to vector store."""
        documents = [
            {"content": "Test document 1", "metadata": {"section": "test"}},
            {"content": "Test document 2", "metadata": {"section": "test2"}},
        ]

        count = vector_store.add_documents(documents)
        assert count == 2
        assert len(vector_store.documents) == 2

    def test_search_returns_results(self, vector_store):
        """Test that search returns results."""
        documents = [
            {"content": "Parking is available downtown", "metadata": {"section": "info"}},
            {"content": "Rates are $5 per hour", "metadata": {"section": "pricing"}},
        ]
        vector_store.add_documents(documents)

        results = vector_store.search("parking rates", top_k=2)
        assert len(results) > 0
        assert "content" in results[0]
        assert "score" in results[0]

    def test_search_respects_top_k(self, vector_store):
        """Test that search respects top_k parameter."""
        documents = [
            {"content": f"Test document {i}", "metadata": {"id": i}}
            for i in range(10)
        ]
        vector_store.add_documents(documents)

        results = vector_store.search("test", top_k=3)
        assert len(results) == 3

    def test_get_collection_info(self, vector_store):
        """Test getting collection information."""
        vector_store.add_documents([
            {"content": "Test", "metadata": {}}
        ])

        info = vector_store.get_collection_info()
        assert info["name"] == "test_collection"
        assert info["num_entities"] == 1

    def test_drop_collection(self, vector_store):
        """Test dropping collection."""
        vector_store.add_documents([{"content": "Test", "metadata": {}}])
        assert len(vector_store.documents) == 1

        vector_store.drop_collection()
        assert vector_store.documents == []

    def test_search_empty_collection(self, vector_store):
        """Test searching empty collection returns empty list."""
        results = vector_store.search("test query")
        assert results == []


class TestVectorStoreFunctions:
    """Tests for vector store utility functions."""

    @patch('src.core.vector_store.InMemoryVectorStore')
    def test_get_vector_store_in_memory(self, mock_store):
        """Test getting in-memory vector store."""
        get_vector_store(use_in_memory=True)
        mock_store.assert_called_once()

    def test_add_documents_batch(self):
        """Test adding documents in batches."""
        store = InMemoryVectorStore("test")
        store.create_collection(overwrite=True)

        # Add more documents than default batch size
        documents = [
            {"content": f"Document {i}", "metadata": {"id": i}}
            for i in range(150)
        ]

        count = store.add_documents(documents, batch_size=100)
        assert count == 150


class TestVectorStoreIntegration:
    """Integration tests for vector store."""

    def test_document_retrieval_relevance(self):
        """Test that retrieved documents are relevant to query."""
        store = InMemoryVectorStore("test")
        store.create_collection(overwrite=True)

        documents = [
            {"content": "Parking hours are 6 AM to 11 PM", "metadata": {"section": "hours"}},
            {"content": "Parking rates are $3 per hour", "metadata": {"section": "pricing"}},
            {"content": "We are located at 123 Main Street", "metadata": {"section": "location"}},
            {"content": "EV charging is available on level 1", "metadata": {"section": "amenities"}},
        ]
        store.add_documents(documents)

        # Search for pricing info
        results = store.search("how much does parking cost", top_k=2)
        assert len(results) > 0

        # The pricing document should be in results
        content_texts = [r["content"] for r in results]
        assert any("$3" in text or "rate" in text.lower() for text in content_texts)

    def test_search_with_metadata(self):
        """Test that search returns metadata."""
        store = InMemoryVectorStore("test")
        store.create_collection(overwrite=True)

        documents = [
            {"content": "Test content", "metadata": {"section": "test_section", "priority": "high"}}
        ]
        store.add_documents(documents)

        results = store.search("test", top_k=1)
        assert len(results) > 0
        assert "metadata" in results[0]
