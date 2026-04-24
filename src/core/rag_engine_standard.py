"""Standard RAG Engine implementing Retrieval-Augmented Generation with proper chunking and reranking.

This module implements a production-ready RAG pipeline following LangChain best practices:
1. Document loading with proper chunking
2. Vector store with embeddings
3. Retrieval with reranking
4. Generation with context
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from langchain_core.embeddings import Embeddings
    from langchain_core.documents import Document
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough, RunnableLambda
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        # Fallback to old import paths
        from langchain.embeddings import Embeddings
        from langchain.schema import Document
        from langchain.schema import BaseRetriever
        from langchain.prompts import ChatPromptTemplate
        from langchain.output_parsers import StrOutputParser
        from langchain.runnables import RunnablePassthrough, RunnableLambda
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        LANGCHAIN_AVAILABLE = False

try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from src.core.llm_handler import LLMHandler
from src.config.settings import get_settings


@dataclass
class RAGResult:
    """Result from RAG query."""
    answer: str
    sources: List[Dict[str, Any]]
    retrieval_latency: float
    rerank_latency: float
    generation_latency: float
    total_latency: float
    num_chunks_retrieved: int
    num_chunks_reranked: int


class DeepSeekEmbeddings(Embeddings):
    """Custom embeddings adapter for DeepSeek/OpenAI."""

    def __init__(self, llm_handler: Optional[LLMHandler] = None):
        """Initialize embeddings."""
        self.llm_handler = llm_handler or LLMHandler()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search documents."""
        embeddings = []
        for text in texts:
            embedding = self.llm_handler.get_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self.llm_handler.get_embedding(text)


class CrossEncoderReranker:
    """Reranker using Cross-Encoder model for better relevance."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_n: int = 3,
    ):
        """Initialize the reranker.

        Args:
            model_name: Cross-Encoder model name
            top_n: Number of top documents to return after reranking
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for reranking. "
                "Install: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.top_n = top_n

        try:
            print(f"🔄 Loading Cross-Encoder model: {model_name}")
            self.model = CrossEncoder(model_name)
            print("✅ Cross-Encoder loaded successfully")
        except Exception as e:
            print(f"⚠️  Failed to load Cross-Encoder: {e}")
            print("   Falling back to no reranking")
            self.model = None

    def rerank(
        self,
        query: str,
        documents: List[Document],
    ) -> Tuple[List[Document], List[float]]:
        """
        Rerank documents based on query relevance.

        Args:
            query: User query
            documents: List of retrieved documents

        Returns:
            Tuple of (reranked_documents, scores)
        """
        if self.model is None:
            return documents, [0.0] * len(documents)

        if not documents:
            return [], []

        # Create query-document pairs
        pairs = [[query, doc.page_content] for doc in documents]

        # Predict scores
        scores = self.model.predict(pairs)

        # Sort by scores
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        # Reorder documents
        reranked_docs = [documents[i] for i, _ in indexed_scores[:self.top_n]]
        reranked_scores = [scores[i] for i, _ in indexed_scores[:self.top_n]]

        return reranked_docs, reranked_scores

    def is_available(self) -> bool:
        """Check if reranker is available."""
        return self.model is not None


class StandardRAGEngine:
    """Production-ready RAG engine with chunking and reranking."""

    def __init__(
        self,
        vector_store=None,
        llm_handler: Optional[LLMHandler] = None,
        system_prompt: Optional[str] = None,
        top_k: int = 10,  # Retrieve more for reranking
        rerank_top_n: int = 3,  # Final top results
        use_rerank: bool = True,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """Initialize the standard RAG engine.

        Args:
            vector_store: Vector store instance
            llm_handler: LLM handler instance
            system_prompt: System prompt for the LLM
            top_k: Number of documents to retrieve for reranking
            rerank_top_n: Number of top documents to return after reranking
            use_rerank: Whether to use reranking
            chunk_size: Document chunk size
            chunk_overlap: Document chunk overlap
        """
        from src.core.vector_store import get_vector_store

        # Initialize components
        self.vector_store = vector_store or get_vector_store(use_in_memory=True)
        self.llm_handler = llm_handler or LLMHandler()
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.use_rerank = use_rerank
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # System prompt
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Initialize embeddings
        self.embeddings = DeepSeekEmbeddings(self.llm_handler)

        # Initialize reranker
        if use_rerank:
            try:
                self.reranker = CrossEncoderReranker(top_n=rerank_top_n)
                self.rerank_available = self.reranker.is_available()
                if self.rerank_available:
                    print("✅ Reranking enabled (Cross-Encoder)")
                else:
                    print("⚠️  Reranking disabled (model not available)")
            except ImportError as e:
                print(f"⚠️  Could not initialize reranker: {e}")
                print(f"   Install: pip install sentence-transformers")
                print(f"   Continuing without reranking...")
                self.reranker = None
                self.rerank_available = False
            except Exception as e:
                print(f"⚠️  Could not initialize reranker: {e}")
                self.reranker = None
                self.rerank_available = False
        else:
            self.reranker = None
            self.rerank_available = False

        # Build LangChain retrieval chain
        if LANGCHAIN_AVAILABLE:
            self._build_chain()
        else:
            print("⚠️  LangChain not available, using manual implementation")
            self.chain = None

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return """You are a helpful parking assistant for CityCenter Parking.

Your role is to:
1. Provide accurate information about parking services (location, hours, pricing, availability)
2. Be friendly, professional, and concise
3. Help users make reservations by collecting necessary information
4. Never share sensitive customer information
5. Politely redirect to parking-related topics if asked about other subjects

Base your answers on the provided context, but speak naturally."""

    def _build_chain(self):
        """Build the LangChain retrieval chain."""
        # Create a custom retriever from our vector store
        self.retriever = StandardRetriever(
            vector_store=self.vector_store,
            top_k=self.top_k,
            llm_handler=self.llm_handler,
        )

        # Create the prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", """Context: {context}

Question: {input}

Please provide a helpful answer based on the information above.""")
        ])

        # Create LLM callable for LangChain
        def llm_callable(prompt_value):
            """Convert prompt value to string and call LLM."""
            # Handle ChatPromptValue or string
            if hasattr(prompt_value, 'to_string'):
                prompt_text = prompt_value.to_string()
            elif hasattr(prompt_value, 'messages'):
                # Extract text from ChatPromptValue
                messages = prompt_value.messages
                prompt_text = "\n".join([msg.content for msg in messages])
            elif isinstance(prompt_value, str):
                prompt_text = prompt_value
            else:
                prompt_text = str(prompt_value)

            return self.llm_handler.generate_response(
                prompt=prompt_text,
                system_prompt=self.system_prompt
            )

        # Build the chain using LangChain 1.0 LCEL
        self.chain = (
            {
                "context": self.retriever | RunnableLambda(self._format_docs),
                "input": RunnablePassthrough()
            }
            | self.prompt
            | RunnableLambda(llm_callable)
            | StrOutputParser()
        )

    def _format_docs(self, docs: List[Document]) -> str:
        """Format documents for context."""
        return "\n\n".join([
            f"[Source {i+1}] {doc.page_content}"
            for i, doc in enumerate(docs)
        ])

    def query(
        self,
        user_query: str,
        use_history: bool = True,
        include_sources: bool = False,
        verbose: bool = False,
    ) -> RAGResult:
        """
        Process a user query using standard RAG pipeline.

        Pipeline:
        1. Retrieve top_k documents
        2. Rerank if enabled
        3. Generate response

        Args:
            user_query: The user's question
            use_history: Whether to include conversation history
            include_sources: Whether to include source references
            verbose: Whether to print detailed information

        Returns:
            RAGResult with answer and metadata.
        """
        start_time = time.time()

        # Step 1: Retrieve documents
        retrieval_start = time.time()
        docs = self.retriever.get_relevant_documents(user_query)
        retrieval_latency = time.time() - retrieval_start

        if verbose and docs:
            print(f"📊 Retrieved {len(docs)} documents")

        # Step 2: Rerank if enabled
        rerank_start = time.time()
        reranked_docs = docs
        rerank_scores = []

        if self.rerank_available and len(docs) > self.rerank_top_n:
            reranked_docs, rerank_scores = self.reranker.rerank(user_query, docs)
            if verbose:
                print(f"🔄 Reranked to {len(reranked_docs)} documents")
                for i, (doc, score) in enumerate(zip(reranked_docs, rerank_scores)):
                    print(f"   {i+1}. Score: {score:.3f} | {doc.page_content[:50]}...")

        rerank_latency = time.time() - rerank_start

        # Update retriever's cached documents for chain
        self.retriever._cached_documents = reranked_docs

        # Step 3: Generate response
        generation_start = time.time()

        if self.chain and LANGCHAIN_AVAILABLE:
            answer = self.chain.invoke(user_query)
        else:
            # Fallback to manual implementation
            context = self._format_docs(reranked_docs)
            prompt = f"""Context: {context}

Question: {user_query}

Please provide a helpful answer based on the information above."""
            answer = self.llm_handler.generate_response(
                prompt=prompt,
                system_prompt=self.system_prompt
            )

        generation_latency = time.time() - generation_start

        # Add sources if requested
        if include_sources and reranked_docs:
            source_refs = self._format_sources(reranked_docs, rerank_scores)
            answer = f"{answer}\n\nSources:\n{source_refs}"

        total_latency = time.time() - start_time

        # Convert documents to dict format
        sources = []
        for doc, score in zip(reranked_docs, rerank_scores):
            sources.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score) if score else 0.0,
            })

        return RAGResult(
            answer=answer,
            sources=sources,
            retrieval_latency=retrieval_latency,
            rerank_latency=rerank_latency,
            generation_latency=generation_latency,
            total_latency=total_latency,
            num_chunks_retrieved=len(docs),
            num_chunks_reranked=len(reranked_docs),
        )

    def _format_sources(
        self,
        docs: List[Document],
        scores: List[float],
    ) -> str:
        """Format sources for display."""
        formatted = []
        for i, (doc, score) in enumerate(zip(docs, scores), 1):
            metadata = doc.metadata
            section = metadata.get("section", "Unknown")
            chunk_id = metadata.get("chunk_id", "N/A")
            formatted.append(
                f"- Source {i}: [{section}] (Chunk: {chunk_id}, Relevance: {score:.3f})"
            )
        return "\n".join(formatted)

    def initialize_with_chunking(
        self,
        force_reload: bool = False,
    ) -> None:
        """
        Initialize vector store with chunked documents.

        Args:
            force_reload: Whether to reload even if already initialized
        """
        from src.data.static_data import get_static_loader
        from src.core.vector_store import initialize_vector_store

        # Initialize vector store
        initialize_vector_store(force_reload=force_reload)

        # Load documents with chunking
        loader = get_static_loader()
        documents = loader.load_documents_with_chunking(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            use_langchain=True,
        )

        # Add documents to vector store
        if hasattr(self.vector_store, 'add_documents'):
            self.vector_store.add_documents(documents)
            print(f"✅ Added {len(documents)} chunked documents to vector store")
        else:
            # For in-memory store
            for doc in documents:
                self.vector_store.documents.append({
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "embedding": None,
                })
            print(f"✅ Added {len(documents)} chunked documents to in-memory store")

    def clear_history(self) -> None:
        """Clear conversation history (placeholder for LangChain memory)."""
        pass

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history (placeholder)."""
        return []

    def set_system_prompt(self, prompt: str) -> None:
        """Update the system prompt."""
        self.system_prompt = prompt
        if LANGCHAIN_AVAILABLE:
            self._build_chain()  # Rebuild chain with new prompt

    def get_statistics(self) -> Dict[str, Any]:
        """Get RAG engine statistics."""
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k_retrieval": self.top_k,
            "rerank_top_n": self.rerank_top_n,
            "rerank_enabled": self.rerank_available,
            "rerank_model": self.reranker.model_name if self.reranker else "N/A",
        }


class StandardRetriever:
    """Standard retriever that wraps vector store with proper interface."""

    def __init__(
        self,
        vector_store: Any,
        top_k: int = 10,
        llm_handler: Optional[LLMHandler] = None,
    ):
        """Initialize the retriever.

        Args:
            vector_store: Vector store instance
            top_k: Number of documents to retrieve
            llm_handler: LLM handler for embeddings
        """
        self.vector_store = vector_store
        self.top_k = top_k
        self.llm_handler = llm_handler or get_llm_handler()
        self._cached_documents = []

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Retrieve relevant documents.

        Args:
            query: Search query

        Returns:
            List of relevant documents.
        """
        results = self.vector_store.search(query=query, top_k=self.top_k)

        documents = []
        for result in results:
            doc = Document(
                page_content=result.get("content", ""),
                metadata=result.get("metadata", {}) if isinstance(result.get("metadata"), dict) else {}
            )
            documents.append(doc)

        self._cached_documents = documents
        return documents

    def __call__(self, query: str) -> List[Document]:
        """Allow callable interface for LangChain."""
        return self.get_relevant_documents(query)


def get_standard_rag_engine(
    use_mock: bool = False,
    use_rerank: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> StandardRAGEngine:
    """
    Get standard RAG engine instance with chunking and reranking.

    Args:
        use_mock: Whether to use mock engine (for testing)
        use_rerank: Whether to enable reranking
        chunk_size: Document chunk size
        chunk_overlap: Document chunk overlap

    Returns:
        StandardRAGEngine instance.
    """
    return StandardRAGEngine(
        use_rerank=use_rerank,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def initialize_standard_rag_engine(
    force_reload: bool = False,
    use_rerank: bool = True,
) -> StandardRAGEngine:
    """
    Initialize standard RAG engine with chunked documents.

    Args:
        force_reload: Whether to reload documents even if already loaded
        use_rerank: Whether to enable reranking

    Returns:
        Initialized StandardRAGEngine instance.
    """
    engine = get_standard_rag_engine(use_rerank=use_rerank)
    engine.initialize_with_chunking(force_reload=force_reload)
    return engine
