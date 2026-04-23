"""RAG Engine implementing Retrieval-Augmented Generation with LangChain 1.0."""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from src.core.llm_handler import LLMHandler
from src.config.settings import get_settings


@dataclass
class RAGResult:
    """Result from RAG query."""
    answer: str
    sources: List[Document]
    retrieval_latency: float
    generation_latency: float
    total_latency: float


class DeepSeekEmbeddings(Embeddings):
    """Custom embeddings adapter for DeepSeek/OpenAI."""

    def __init__(self):
        """Initialize embeddings."""
        from openai import OpenAI
        from src.config.settings import get_settings

        settings = get_settings()
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = "text-embedding-ada-002"  # DeepSeek supports OpenAI-compatible embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search documents."""
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model
            )
            return [item.embedding for item in response.data]
        except Exception:
            # Fallback to simple hash-based embeddings
            return self._fallback_embeddings(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        try:
            response = self.client.embeddings.create(
                input=[text],
                model=self.model
            )
            return response.data[0].embedding
        except Exception:
            return self._fallback_embeddings([text])[0]

    def _fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Fallback to hash-based embeddings for demo."""
        import hashlib
        import struct

        embeddings = []
        for text in texts:
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            embedding = []
            for i in range(1536):  # OpenAI embedding dimension
                byte_index = i % len(hash_bytes)
                value = struct.unpack('B', hash_bytes[byte_index:byte_index+1])[0]
                normalized = (value - 128) / 128.0
                embedding.append(normalized)
            embeddings.append(embedding)
        return embeddings


class RAGEngine:
    """RAG engine using LangChain 1.0 components."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        llm_handler: Optional[LLMHandler] = None,
        system_prompt: Optional[str] = None,
        top_k: int = 3,
    ):
        """Initialize the RAG engine with LangChain."""
        from langchain_community.vectorstores import Milvus
        from src.core.vector_store import get_vector_store

        # Initialize components
        self.vector_store = vector_store or get_vector_store(use_in_memory=True)
        self.llm_handler = llm_handler or LLMHandler()
        self.top_k = top_k

        # System prompt
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Build LangChain retrieval chain
        self._build_chain()

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
        self.retriever = CustomRetriever(
            vector_store=self.vector_store,
            top_k=self.top_k
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

        # Retrieve documents
        retrieval_start = time.time()
        docs = self.retriever.get_relevant_documents(user_query)
        retrieval_latency = time.time() - retrieval_start

        # Generate response
        generation_start = time.time()
        answer = self.chain.invoke(user_query)
        generation_latency = time.time() - generation_start

        # Add sources if requested
        if include_sources and docs:
            source_refs = self._format_sources(docs)
            answer = f"{answer}\n\nSources:\n{source_refs}"

        total_latency = time.time() - start_time

        return RAGResult(
            answer=answer,
            sources=docs,
            retrieval_latency=retrieval_latency,
            generation_latency=generation_latency,
            total_latency=total_latency,
        )

    def _format_sources(self, docs: List[Document]) -> str:
        """Format sources for display."""
        formatted = []
        for i, doc in enumerate(docs, 1):
            metadata = doc.metadata
            formatted.append(f"- Source {i}: {metadata}")
        return "\n".join(formatted)

    def clear_history(self) -> None:
        """Clear conversation history (placeholder for LangChain memory)."""
        pass

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history (placeholder)."""
        return []

    def set_system_prompt(self, prompt: str) -> None:
        """Update the system prompt."""
        self.system_prompt = prompt
        self._build_chain()  # Rebuild chain with new prompt


class CustomRetriever:
    """Simple custom retriever that wraps our vector store without LangChain BaseRetriever."""

    def __init__(self, vector_store: Any, top_k: int = 3):
        """Initialize the retriever."""
        self.vector_store = vector_store
        self.top_k = top_k

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Retrieve relevant documents (public method for LangChain compatibility)."""
        results = self.vector_store.search(query=query, top_k=self.top_k)

        documents = []
        for result in results:
            doc = Document(
                page_content=result.get("content", ""),
                metadata=result.get("metadata", {})
            )
            documents.append(doc)

        return documents

    def __call__(self, query: str) -> List[Document]:
        """Allow callable interface for LangChain."""
        return self.get_relevant_documents(query)


def get_rag_engine(use_mock: bool = False) -> RAGEngine:
    """Get RAG engine instance."""
    return RAGEngine()


def initialize_rag_engine() -> RAGEngine:
    """Initialize RAG engine with vector store."""
    from src.core.vector_store import initialize_vector_store

    # Initialize vector store
    initialize_vector_store()

    # Create and return RAG engine
    return get_rag_engine()
