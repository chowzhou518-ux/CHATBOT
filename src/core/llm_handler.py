"""LLM handler for interacting with various LLM providers (DeepSeek, Anthropic, OpenAI)."""

import time
from typing import Optional, List, Dict, Any

from src.config.settings import get_settings

# Try to import OpenAI SDK (for DeepSeek and OpenAI)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try to import Anthropic SDK (for Claude)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMHandler:
    """Handler for LLM API interactions (supports DeepSeek, Anthropic, OpenAI)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize the LLM handler."""
        settings = get_settings()

        # Get provider from settings or parameter
        self.provider = provider or settings.llm_provider
        self.base_url = base_url or settings.llm_base_url

        # Configure based on provider
        if self.provider == "deepseek":
            self.api_key = api_key or settings.deepseek_api_key
            self.model = model or settings.default_model
            if not self.api_key:
                raise ValueError("DEEPSEEK_API_KEY must be set in environment variables")

            if not OPENAI_AVAILABLE:
                raise ImportError("openai package is required for DeepSeek. Install: pip install openai")

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            self._use_openai_format = True

        elif self.provider == "openai":
            self.api_key = api_key or getattr(settings, 'openai_api_key', None)
            self.model = model or "gpt-3.5-turbo"
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY must be set in environment variables")

            if not OPENAI_AVAILABLE:
                raise ImportError("openai package is required")

            self.client = OpenAI(api_key=self.api_key)
            self._use_openai_format = True

        elif self.provider == "anthropic":
            self.api_key = api_key or getattr(settings, 'anthropic_api_key', None)
            self.model = model or "claude-3-5-sonnet-20241022"
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY must be set in environment variables")

            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package is required")

            self.client = Anthropic(api_key=self.api_key)
            self._use_openai_format = False

        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Choose from: deepseek, openai, anthropic")

        self.temperature = temperature if temperature is not None else settings.temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.max_tokens

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user's message
            system_prompt: Optional system prompt for context
            context: Additional context to include
            stream: Whether to stream the response

        Returns:
            The generated response text.
        """
        # Build the message content
        message_content = prompt
        if context:
            message_content = f"Context:\n{context}\n\nUser Question:\n{prompt}"

        try:
            start_time = time.time()

            if self._use_openai_format:
                return self._generate_openai(message_content, system_prompt, stream)
            else:
                return self._generate_anthropic(message_content, system_prompt, stream)

        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}"

    def _generate_openai(
        self,
        message_content: str,
        system_prompt: Optional[str],
        stream: bool,
    ) -> str:
        """Generate response using OpenAI-compatible API (DeepSeek, OpenAI)."""
        messages = [{"role": "user", "content": message_content}]

        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        if stream:
            return self._stream_openai(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return response.choices[0].message.content

    def _generate_anthropic(
        self,
        message_content: str,
        system_prompt: Optional[str],
        stream: bool,
    ) -> str:
        """Generate response using Anthropic API."""
        messages = [{"role": "user", "content": message_content}]

        if stream:
            return self._stream_anthropic(messages, system_prompt)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages,
        )

        return response.content[0].text

    def _stream_openai(self, messages: List[Dict[str, str]]) -> str:
        """Stream response from OpenAI-compatible API."""
        full_response = ""

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content

        return full_response

    def _stream_anthropic(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
    ) -> str:
        """Stream response from Anthropic API."""
        full_response = ""

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response += text

        return full_response

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Any:
        """
        Generate a response with tool use capabilities.

        Args:
            messages: Conversation history
            tools: List of available tools
            system_prompt: Optional system prompt

        Returns:
            The response which may include tool calls.
        """
        try:
            if self._use_openai_format:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            else:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )
            return response
        except Exception as e:
            raise RuntimeError(f"Failed to generate response with tools: {e}")

    def continue_after_tool_use(
        self,
        messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Any:
        """
        Continue conversation after tool use.

        Args:
            messages: Original conversation history
            tool_results: Results from tool execution
            tools: List of available tools
            system_prompt: Optional system prompt

        Returns:
            The response after tool use.
        """
        # Build new message list with tool results
        new_messages = messages + [
            {"role": "assistant", "content": "Let me check that information for you."},
            {
                "role": "user",
                "content": str(tool_results),
            },
        ]

        try:
            if self._use_openai_format:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=new_messages,
                    tools=tools,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            else:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=new_messages,
                    tools=tools,
                )
            return response
        except Exception as e:
            raise RuntimeError(f"Failed to continue after tool use: {e}")

    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text (using a simple hash-based approach for demo).
        In production, use an actual embedding service.

        Args:
            text: Text to embed

        Returns:
            Embedding vector.
        """
        # Note: This is a placeholder. In production, use an actual embedding service
        # like DeepSeek embeddings, OpenAI embeddings, or a local model.
        import hashlib
        import struct

        # Create a simple hash-based embedding (for demo purposes)
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to 384-dimensional vector (matching sentence-transformers default)
        embedding = []
        for i in range(384):
            byte_index = i % len(hash_bytes)
            value = struct.unpack('B', hash_bytes[byte_index:byte_index+1])[0]
            normalized = (value - 128) / 128.0  # Normalize to [-1, 1]
            embedding.append(normalized)

        return embedding


class ChatMessage:
    """Represents a chat message."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[float] = None,
    ):
        self.role = role  # "user", "assistant", "system"
        self.content = content
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "role": self.role,
            "content": self.content,
        }


class ConversationHistory:
    """Manages conversation history with context limit."""

    def __init__(self, max_length: int = 10):
        self.max_length = max_length
        self.messages: List[ChatMessage] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to history."""
        self.messages.append(ChatMessage(role, content))
        self._trim()

    def _trim(self) -> None:
        """Keep only the most recent messages."""
        if len(self.messages) > self.max_length:
            self.messages = self.messages[-self.max_length:]

    def get_context(self, include_system: bool = False) -> str:
        """Get conversation context as string."""
        context_parts = []
        for msg in self.messages:
            if msg.role == "system" and not include_system:
                continue
            context_parts.append(f"{msg.role.capitalize()}: {msg.content}")

        return "\n\n".join(context_parts)

    def to_list(self) -> List[Dict[str, str]]:
        """Convert to list of dictionaries for API."""
        return [msg.to_dict() for msg in self.messages]

    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []

    @property
    def last_user_message(self) -> Optional[str]:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None


def get_llm_handler() -> LLMHandler:
    """Get or create global LLM handler instance."""
    return LLMHandler()
