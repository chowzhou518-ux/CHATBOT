"""Vector store implementation using Milvus for semantic search."""

import time
from typing import List, Dict, Any, Optional, Tuple
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)

from src.config.settings import get_settings
from src.core.llm_handler import get_llm_handler


class VectorStore:
    """Milvus-based vector store for semantic document retrieval."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        embedding_dim: int = 384,
    ):
        """Initialize the vector store."""
        settings = get_settings()
        self.collection_name = collection_name or settings.collection_name
        self.embedding_dim = embedding_dim
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.llm_handler = get_llm_handler()

        self._connect()
        self.collection = None

    def _connect(self) -> None:
        """Connect to Milvus server."""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Milvus at {self.host}:{self.port}: {e}")

    def create_collection(self, overwrite: bool = False) -> None:
        """Create a new collection for document storage."""
        # Check if collection exists
        if utility.has_collection(self.collection_name):
            if overwrite:
                utility.drop_collection(self.collection_name)
            else:
                self.collection = Collection(self.collection_name)
                return

        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
        ]

        schema = CollectionSchema(
            fields=fields,
            description=f"Parking knowledge base: {self.collection_name}",
        )

        # Create collection
        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
        )

        # Create index on embedding field
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }

        self.collection.create_index(
            field_name="embedding",
            index_params=index_params,
        )

    def add_documents(
        self,
        documents: List[Dict[str, str]],
        batch_size: int = 100,
    ) -> int:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents with 'content' and optional 'metadata'
            batch_size: Number of documents to insert at once

        Returns:
            Number of documents inserted.
        """
        if self.collection is None:
            self.collection = Collection(self.collection_name)

        inserted_count = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            document_ids = []
            contents = []
            metadatas = []
            embeddings = []

            for idx, doc in enumerate(batch):
                doc_id = f"doc_{int(time.time() * 1000)}_{idx}"
                content = doc.get("content", "")
                metadata = str(doc.get("metadata", {}))

                document_ids.append(doc_id)
                contents.append(content)
                metadatas.append(metadata)

                # Generate embedding
                embedding = self.llm_handler.get_embedding(content)
                embeddings.append(embedding)

            # Insert batch
            data = [
                document_ids,
                contents,
                metadatas,
                embeddings,
            ]

            try:
                insert_result = self.collection.insert(data)
                inserted_count += len(batch)
            except Exception as e:
                print(f"Error inserting batch: {e}")

        # Flush to ensure data is persisted
        self.collection.flush()
        return inserted_count

    def search(
        self,
        query: str,
        top_k: int = 5,
        output_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query: Search query
            top_k: Number of results to return
            output_fields: Fields to include in results

        Returns:
            List of matching documents with scores.
        """
        if self.collection is None:
            self.collection = Collection(self.collection_name)

        # Load collection into memory
        self.collection.load()

        # Generate query embedding
        query_embedding = self.llm_handler.get_embedding(query)

        # Define search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }

        # Perform search
        if output_fields is None:
            output_fields = ["document_id", "content", "metadata"]

        try:
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=output_fields,
            )
        except Exception as e:
            print(f"Search error: {e}")
            return []

        # Format results
        formatted_results = []
        for hit in results[0]:
            formatted_results.append({
                "content": hit.entity.get("content"),
                "metadata": hit.entity.get("metadata"),
                "score": hit.score,
                "document_id": hit.entity.get("document_id"),
            })

        return formatted_results

    def delete_by_document_id(self, document_id: str) -> bool:
        """Delete a document by its ID."""
        if self.collection is None:
            return False

        try:
            expr = f'document_id == "{document_id}"'
            self.collection.delete(expr)
            return True
        except Exception as e:
            print(f"Delete error: {e}")
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        if self.collection is None:
            return {}

        self.collection.load()
        stats = self.collection.describe()

        return {
            "name": stats.get("name"),
            "description": stats.get("description"),
            "num_entities": self.collection.num_entities,
        }

    def drop_collection(self) -> bool:
        """Drop the entire collection."""
        try:
            utility.drop_collection(self.collection_name)
            self.collection = None
            return True
        except Exception as e:
            print(f"Drop collection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        connections.disconnect("default")


class InMemoryVectorStore(VectorStore):
    """In-memory fallback for when Milvus is not available."""

    def __init__(self, collection_name: str = "temp_collection"):
        """Initialize in-memory store."""
        self.documents: List[Dict[str, Any]] = []
        self.collection_name = collection_name
        self.llm_handler = get_llm_handler()
        self._embedding_cache: Dict[str, List[float]] = {}

    def _connect(self) -> None:
        """No connection needed for in-memory."""
        pass

    def create_collection(self, overwrite: bool = False) -> None:
        """Create in-memory collection."""
        if overwrite:
            self.documents = []

    def add_documents(self, documents: List[Dict[str, str]], batch_size: int = 100) -> int:
        """Add documents to memory (without pre-generating embeddings to save memory)."""
        for doc in documents:
            content = doc.get("content", "")
            # Don't pre-generate embeddings! Generate on search instead.
            self.documents.append({
                "content": content,
                "metadata": doc.get("metadata", {}),
                "embedding": None,  # Will be generated on first search
            })

        return len(documents)

    def search(
        self,
        query: str,
        top_k: int = 5,
        output_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search using cosine similarity with lazy embedding generation."""
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        if not self.documents:
            return []

        # Get query embedding
        query_embedding = self.llm_handler.get_embedding(query)

        # Calculate similarities (generate embeddings on-the-fly if needed)
        similarities = []
        for doc in self.documents:
            # Generate embedding if not cached
            if doc["embedding"] is None:
                doc["embedding"] = self.llm_handler.get_embedding(doc["content"])

            sim = cosine_similarity(
                [query_embedding],
                [doc["embedding"]],
            )[0][0]
            similarities.append((sim, doc))

        # Sort by similarity
        similarities.sort(key=lambda x: x[0], reverse=True)

        # Return top_k results
        results = []
        for score, doc in similarities[:top_k]:
            results.append({
                "content": doc["content"],
                "metadata": str(doc.get("metadata", {})),
                "score": float(score),
                "document_id": "in_memory",
            })

        return results

    def disconnect(self) -> None:
        """No disconnect needed."""
        pass

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the in-memory collection."""
        return {
            "name": self.collection_name,
            "description": "In-memory vector store",
            "num_entities": len(self.documents),
        }


# Global cache for InMemoryVectorStore (singleton pattern)
_in_memory_store_cache: Optional[InMemoryVectorStore] = None
_in_memory_store_initialized = False


def get_vector_store(use_in_memory: bool = False) -> VectorStore:
    """Get vector store instance (cached for in-memory store)."""
    global _in_memory_store_cache, _in_memory_store_initialized

    if use_in_memory:
        # Use cached instance for InMemoryVectorStore
        if _in_memory_store_cache is None:
            _in_memory_store_cache = InMemoryVectorStore()
        return _in_memory_store_cache
    return VectorStore()


def initialize_vector_store(force_reload: bool = False) -> VectorStore:
    """
    Initialize the vector store with sample data (without pre-generating embeddings).

    Args:
        force_reload: Whether to reload documents even if collection exists

    Returns:
        Initialized vector store.
    """
    global _in_memory_store_initialized

    from src.data.static_data import get_static_loader

    store = get_vector_store(use_in_memory=True)

    # Only initialize if empty or force reload
    if not force_reload and _in_memory_store_initialized:
        return store

    # Create collection
    store.create_collection(overwrite=True)

    # Load and add documents (embeddings will be generated on search)
    loader = get_static_loader()
    all_documents = loader.load_documents()

    # 🔑 Only load the most critical documents to save memory
    # Priority: pricing, hours, location, booking process
    critical_sections = [
        "价格费率", "Pricing",
        "营业时间", "Working Hours",
        "位置", "Location",
        "预订和预订流程", "Booking and Reservation Process",
        "车位可用性", "Space Availability",
    ]

    documents = []
    for doc in all_documents:
        metadata = doc.get("metadata", {})
        section = metadata.get("section", "")

        # Only include critical sections
        if any(cs in section for cs in critical_sections):
            documents.append(doc)

    # Add documents WITHOUT pre-generating embeddings
    for doc in documents:
        content = doc.get("content", "")
        store.documents.append({
            "content": content,
            "metadata": doc.get("metadata", {}),
            "embedding": None,  # Will be generated on search
        })

    _in_memory_store_initialized = True
    print(f"✅ Initialized vector store with {len(documents)} critical documents (embeddings generated on search)")

    return store
