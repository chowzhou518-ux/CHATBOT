"""LangChain adapter for LLM handler to work with LangChain agents."""

from typing import Optional, List, Dict, Any
from langchain_core.language_models.llms import BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult, ChatResult, ChatGeneration
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

from src.core.llm_handler import LLMHandler, get_llm_handler


class LangChainLLMAdapter(BaseChatModel):
    """
    Adapter to make LLMHandler compatible with LangChain.

    This allows the existing LLMHandler to work with LangChain agents,
    chains, and other LangChain components.
    """

    def __init__(
        self,
        llm_handler: Optional[LLMHandler] = None,
        **kwargs
    ):
        """Initialize the adapter."""
        super().__init__(**kwargs)
        self.llm_handler = llm_handler or get_llm_handler()

    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return f"llm_adapter_{self.llm_handler.provider}"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate a response using the LLM handler.

        Args:
            messages: List of messages (LangChain format)
            stop: Optional stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional arguments

        Returns:
            ChatResult with the generated message
        """
        # Convert LangChain messages to the format expected by LLMHandler
        system_prompt = None
        user_prompts = []

        for message in messages:
            if isinstance(message, SystemMessage):
                system_prompt = message.content
            elif isinstance(message, HumanMessage):
                user_prompts.append(message.content)
            elif isinstance(message, AIMessage):
                # For now, ignore AI messages in history
                pass

        # Combine user prompts
        combined_prompt = "\n".join(user_prompts) if user_prompts else ""

        # Generate response using LLMHandler
        response_text = self.llm_handler.generate_response(
            prompt=combined_prompt,
            system_prompt=system_prompt,
            stream=False,
        )

        # Create AIMessage
        ai_message = AIMessage(content=response_text)

        # Create ChatGeneration
        generation = ChatGeneration(message=ai_message)

        # Return ChatResult
        return ChatResult(generations=[generation])

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get identifying parameters."""
        return {
            "provider": self.llm_handler.provider,
            "model": self.llm_handler.model,
            "temperature": self.llm_handler.temperature,
        }


def create_langchain_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> BaseChatModel:
    """
    Create a LangChain-compatible chat model.

    This function provides two options:
    1. Use the adapter (works with existing LLMHandler)
    2. Use native LangChain integrations (recommended for production)

    Args:
        provider: LLM provider (deepseek, openai, anthropic)
        model: Model name
        **kwargs: Additional arguments

    Returns:
        LangChain-compatible chat model
    """
    # Try to use native LangChain integrations first (better performance)
    try:
        from langchain_openai import ChatOpenAI
        from langchain_anthropic import ChatAnthropic
        from src.config.settings import get_settings

        settings = get_settings()
        provider = provider or settings.llm_provider

        if provider in ["deepseek", "openai"]:
            # Use ChatOpenAI for OpenAI-compatible APIs
            return ChatOpenAI(
                model=model or settings.default_model,
                api_key=settings.deepseek_api_key if provider == "deepseek" else getattr(settings, 'openai_api_key', None),
                base_url=settings.llm_base_url if provider == "deepseek" else None,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                **kwargs
            )
        elif provider == "anthropic":
            # Use ChatAnthropic for Claude
            return ChatAnthropic(
                model=model or "claude-3-5-sonnet-20241022",
                api_key=getattr(settings, 'anthropic_api_key', None),
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                **kwargs
            )

    except ImportError as e:
        print(f"⚠️  Native LangChain integrations not available: {e}")
        print("   Falling back to adapter mode")

    # Fallback to adapter
    return LangChainLLMAdapter(**kwargs)


def get_langchain_llm() -> BaseChatModel:
    """Get a LangChain-compatible LLM instance."""
    return create_langchain_chat_model()


# Convenience function for backward compatibility
def get_llm_for_agent():
    """Get LLM suitable for use with LangChain agents."""
    return get_langchain_llm()