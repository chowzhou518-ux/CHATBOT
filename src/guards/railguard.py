"""Guardrails mechanism for chatbot safety and data protection."""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from src.guards.filters import PIIFilter, get_pii_filter, get_input_sanitizer


class GuardrailType(str, Enum):
    """Types of guardrails."""
    PII_PROTECTION = "pii_protection"
    TOPIC_FILTERING = "topic_filtering"
    CONTENT_SAFETY = "content_safety"
    OUTPUT_VALIDATION = "output_validation"
    INPUT_SANITIZATION = "input_sanitization"


@dataclass
class GuardrailResult:
    """Result from guardrail check."""
    passed: bool
    modified_content: Optional[str] = None
    violation_type: Optional[str] = None
    reason: Optional[str] = None


class TopicFilter:
    """Filter to keep conversations within allowed topics."""

    # Allowed topics for parking chatbot
    ALLOWED_TOPICS = {
        "parking", "garage", "facility", "location", "address", "directions",
        "hours", "open", "close", "time", "schedule", "availability",
        "price", "rate", "cost", "fee", "payment", "reservation", "booking",
        "space", "spot", "vehicle", "car", "motorcycle", "ev", "electric",
        "charging", "accessible", "handicap", "covered", "security",
        "license", "plate", "reservation", "cancel", "refund",
    }

    # Blocked topics
    BLOCKED_TOPICS = {
        "illegal", "drug", "weapon", "hack", "exploit", "malware",
        "political", "religion", "gambling", "adult",
    }

    def __init__(self):
        """Compile topic keywords."""
        self.allowed_patterns = [
            re.compile(rf'\b{topic}\w*\b', re.IGNORECASE)
            for topic in self.ALLOWED_TOPICS
        ]
        self.blocked_patterns = [
            re.compile(rf'\b{topic}\w*\b', re.IGNORECASE)
            for topic in self.BLOCKED_TOPICS
        ]

    def is_allowed_topic(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text is within allowed topics.

        Returns:
            Tuple of (is_allowed, reason)
        """
        text_lower = text.lower()

        # Check for blocked topics first
        for pattern in self.blocked_patterns:
            if pattern.search(text):
                return False, "Topic is not appropriate for this assistant"

        # Check for allowed topics
        for pattern in self.allowed_patterns:
            if pattern.search(text):
                return True, None

        # If no clear topic, allow but note it
        return True, "Topic unclear but not explicitly blocked"

    def get_topic_score(self, text: str) -> float:
        """
        Get relevance score to parking domain.

        Returns:
            Score between 0 and 1.
        """
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Count matching words
        allowed_matches = sum(1 for word in words if any(
            topic in word for topic in self.ALLOWED_TOPICS
        ))

        # Normalize by text length
        if not words:
            return 0.0

        return min(allowed_matches / len(words), 1.0)


class ContentSafetyFilter:
    """Filter for harmful or inappropriate content."""

    HARMFUL_PATTERNS = [
        (r'(\bhow\s+to\s+(?:steal|break\s+into|hack|damage)\b)', "harmful instructions"),
        (r'(\bkill\b.*\b(yourself|someone)\b)', "self-harm or violence"),
        (r'(\bthreat\b|\bhurt\b|\battack\b)', "threatening language"),
    ]

    def __init__(self):
        """Compile harmful patterns."""
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in self.HARMFUL_PATTERNS
        ]

    def is_safe(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if content is safe.

        Returns:
            Tuple of (is_safe, reason)
        """
        for pattern, reason in self.compiled_patterns:
            if pattern.search(text):
                return False, f"Content may contain: {reason}"

        return True, None


class OutputValidator:
    """Validate chatbot outputs."""

    def __init__(self, pii_filter: Optional[PIIFilter] = None):
        """Initialize output validator."""
        self.pii_filter = pii_filter or get_pii_filter()

    def validate_output(self, text: str) -> GuardrailResult:
        """
        Validate output for issues.

        Returns:
            GuardrailResult with validation status.
        """
        # Check for PII leakage
        pii_summary = self.pii_filter.extract_pii_summary(text)
        if pii_summary:
            # Mask the PII and return modified content
            modified = self.pii_filter.redact_pii(text)
            return GuardrailResult(
                passed=False,
                modified_content=modified,
                violation_type="pii_leakage",
                reason=f"PII detected in output: {pii_summary}",
            )

        # Check for empty or very short responses
        if len(text.strip()) < 10:
            return GuardrailResult(
                passed=False,
                violation_type="empty_response",
                reason="Response is too short",
            )

        # Check for repetitive text
        words = text.lower().split()
        if len(words) > 10 and len(set(words)) < len(words) * 0.3:
            return GuardrailResult(
                passed=False,
                violation_type="repetitive",
                reason="Response appears too repetitive",
            )

        return GuardrailResult(passed=True)


class GuardrailChain:
    """Chain of guardrails to apply."""

    def __init__(
        self,
        pii_filter: Optional[PIIFilter] = None,
        topic_filter: Optional[TopicFilter] = None,
        safety_filter: Optional[ContentSafetyFilter] = None,
        output_validator: Optional[OutputValidator] = None,
        enabled_guards: Optional[Set[GuardrailType]] = None,
    ):
        """Initialize guardrail chain."""
        self.pii_filter = pii_filter or get_pii_filter()
        self.topic_filter = topic_filter or TopicFilter()
        self.safety_filter = safety_filter or ContentSafetyFilter()
        self.output_validator = output_validator or OutputValidator(self.pii_filter)
        self.input_sanitizer = get_input_sanitizer()

        # Default: enable all guards
        self.enabled_guards = enabled_guards or set(GuardrailType)

    def check_input(self, text: str) -> GuardrailResult:
        """
        Apply all input guardrails.

        Args:
            text: User input

        Returns:
            GuardrailResult with check status.
        """
        original_text = text
        modified_text = text
        violations = []

        # Input sanitization
        if GuardrailType.INPUT_SANITIZATION in self.enabled_guards:
            modified_text = self.input_sanitizer.sanitize(modified_text)
            if modified_text != original_text:
                violations.append("input_sanitized")

        # Topic filtering
        if GuardrailType.TOPIC_FILTERING in self.enabled_guards:
            is_allowed, reason = self.topic_filter.is_allowed_topic(modified_text)
            if not is_allowed:
                return GuardrailResult(
                    passed=False,
                    violation_type="topic_violation",
                    reason=reason,
                )

        # Content safety
        if GuardrailType.CONTENT_SAFETY in self.enabled_guards:
            is_safe, reason = self.safety_filter.is_safe(modified_text)
            if not is_safe:
                return GuardrailResult(
                    passed=False,
                    violation_type="safety_violation",
                    reason=reason,
                )

        # PII detection (for logging/redaction)
        if GuardrailType.PII_PROTECTION in self.enabled_guards:
            if self.pii_filter.contains_pii(modified_text):
                violations.append("pii_detected")
                # Don't block, but note it

        if violations:
            return GuardrailResult(
                passed=True,
                modified_content=modified_text,
                violation_type=", ".join(violations),
                reason="Input processed with warnings",
            )

        return GuardrailResult(
            passed=True,
            modified_content=modified_text or None,
        )

    def check_output(self, text: str) -> GuardrailResult:
        """
        Apply all output guardrails.

        Args:
            text: Chatbot output

        Returns:
            GuardrailResult with check status.
        """
        if GuardrailType.OUTPUT_VALIDATION not in self.enabled_guards:
            return GuardrailResult(passed=True)

        # PII protection
        if GuardrailType.PII_PROTECTION in self.enabled_guards:
            pii_result = self.output_validator.validate_output(text)
            if not pii_result.passed:
                return pii_result

        # General validation
        return self.output_validator.validate_output(text)

    def protect_pii_in_context(self, text: str) -> str:
        """
        Protect PII in context before sending to LLM.

        Args:
            text: Context text

        Returns:
            Text with PII redacted.
        """
        if GuardrailType.PII_PROTECTION not in self.enabled_guards:
            return text

        return self.pii_filter.redact_pii(text)

    def get_topic_relevance(self, text: str) -> float:
        """Get topic relevance score."""
        return self.topic_filter.get_topic_score(text)


class GuardRailHandler:
    """Main handler for guardrails in chatbot."""

    def __init__(
        self,
        guardrail_chain: Optional[GuardrailChain] = None,
        block_on_violation: bool = False,
    ):
        """Initialize guardrail handler."""
        self.chain = guardrail_chain or GuardrailChain()
        self.block_on_violation = block_on_violation
        self.violation_count = 0
        self.total_checks = 0

    def process_input(self, user_input: str) -> Tuple[str, Optional[str]]:
        """
        Process user input through guardrails.

        Returns:
            Tuple of (processed_input, error_message)
        """
        self.total_checks += 1
        result = self.chain.check_input(user_input)

        if not result.passed:
            self.violation_count += 1
            if self.block_on_violation:
                return "", self._get_friendly_error(result)

        processed = result.modified_content or user_input
        return processed, None

    def process_output(self, bot_output: str) -> Tuple[str, Optional[str]]:
        """
        Process bot output through guardrails.

        Returns:
            Tuple of (processed_output, warning_message)
        """
        result = self.chain.check_output(bot_output)

        if not result.passed:
            self.violation_count += 1
            # Return modified output with warning
            modified = result.modified_content or bot_output
            return modified, self._get_friendly_warning(result)

        return bot_output, None

    def _get_friendly_error(self, result: GuardrailResult) -> str:
        """Get user-friendly error message."""
        messages = {
            "topic_violation": "I'm designed to help with parking-related questions. Could you ask something about our parking services?",
            "safety_violation": "I'm not able to help with that request.",
        }
        return messages.get(
            result.violation_type,
            "I couldn't process that request. Please try rephrasing."
        )

    def _get_friendly_warning(self, result: GuardrailResult) -> str:
        """Get user-friendly warning message."""
        if result.violation_type == "pii_leakage":
            return "(Note: Some information was redacted for privacy protection)"
        return ""

    def get_statistics(self) -> Dict[str, Any]:
        """Get guardrail statistics."""
        return {
            "total_checks": self.total_checks,
            "violations": self.violation_count,
            "violation_rate": self.violation_count / self.total_checks if self.total_checks > 0 else 0,
        }


# Global instance
_guardrail_handler: Optional[GuardRailHandler] = None


def get_guardrail_handler(block_on_violation: bool = False) -> GuardRailHandler:
    """Get global guardrail handler instance."""
    global _guardrail_handler
    if _guardrail_handler is None:
        _guardrail_handler = GuardRailHandler(block_on_violation=block_on_violation)
    return _guardrail_handler
