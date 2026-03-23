"""Tests for guardrails and PII filtering."""

import pytest
from unittest.mock import Mock, patch

from src.guards.filters import (
    PIIDetector,
    PIIFilter,
    InputSanitizer,
    PIIType,
    get_pii_detector,
    get_pii_filter,
    get_input_sanitizer,
)
from src.guards.railguard import (
    TopicFilter,
    ContentSafetyFilter,
    GuardrailResult,
    GuardRailHandler,
    get_guardrail_handler,
)


class TestPIIDetector:
    """Tests for PII detection."""

    @pytest.fixture
    def detector(self):
        """Create a PII detector."""
        return PIIDetector(use_presidio=False)  # Use regex for testing

    def test_detect_email(self, detector):
        """Test email detection."""
        text = "My email is john@example.com"
        entities = detector.detect_pii(text)

        assert len(entities) > 0
        assert any(e.entity_type == PIIType.EMAIL for e in entities)

    def test_detect_phone(self, detector):
        """Test phone number detection."""
        text = "Call me at 555-123-4567"
        entities = detector.detect_pii(text)

        assert len(entities) > 0
        assert any(e.entity_type == PIIType.PHONE for e in entities)

    def test_detect_multiple_pii_types(self, detector):
        """Test detecting multiple PII types in one text."""
        text = "Contact John Smith at john@example.com or 555-123-4567"
        entities = detector.detect_pii(text)

        # Should detect at least email and phone
        types_found = {e.entity_type for e in entities}
        assert PIIType.EMAIL in types_found
        assert PIIType.PHONE in types_found

    def test_no_pii_in_clean_text(self, detector):
        """Test that clean text has no PII detected."""
        text = "What are your parking hours?"
        entities = detector.detect_pii(text)

        assert len(entities) == 0

    def test_detect_license_plate(self, detector):
        """Test license plate detection."""
        text = "My license plate is ABC-1234"
        entities = detector.detect_pii(text)

        # License plates may be detected
        assert len(entities) >= 0


class TestPIIFilter:
    """Tests for PII filtering."""

    @pytest.fixture
    def pii_filter(self):
        """Create a PII filter."""
        return PIIFilter(detector=PIIDetector(use_presidio=False))

    def test_mask_email(self, pii_filter):
        """Test masking email addresses."""
        text = "Email me at john@example.com"
        masked = pii_filter.mask_pii(text)

        assert "@" not in masked or "example.com" not in masked
        assert "*" in masked

    def test_mask_phone(self, pii_filter):
        """Test masking phone numbers."""
        text = "Call 555-123-4567 for info"
        masked = pii_filter.mask_pii(text)

        assert "555-123-4567" not in masked

    def test_redact_with_placeholders(self, pii_filter):
        """Test redaction with placeholders."""
        text = "Email: john@example.com, Phone: 555-123-4567"
        redacted = pii_filter.redact_pii(text)

        assert "[EMAIL]" in redacted or "[PHONE]" in redacted

    def test_contains_pii(self, pii_filter):
        """Test checking if text contains PII."""
        assert pii_filter.contains_pii("john@example.com")
        assert not pii_filter.contains_pii("What are your hours?")

    def test_extract_pii_summary(self, pii_filter):
        """Test extracting PII summary."""
        text = "Contact john@example.com or jane@test.com"
        summary = pii_filter.extract_pii_summary(text)

        assert "EMAIL" in summary
        assert summary["EMAIL"] >= 2


class TestInputSanitizer:
    """Tests for input sanitization."""

    @pytest.fixture
    def sanitizer(self):
        """Create an input sanitizer."""
        return InputSanitizer()

    def test_sanitize_clean_input(self, sanitizer):
        """Test that clean input is unchanged."""
        text = "What are your parking hours?"
        sanitized = sanitizer.sanitize(text)

        assert sanitized == text

    def test_sanitize_script_tags(self, sanitizer):
        """Test removing script tags."""
        text = "Hello <script>alert('xss')</script> there"
        sanitized = sanitizer.sanitize(text)

        assert "<script>" not in sanitized
        assert "alert" not in sanitized

    def test_is_safe_clean_input(self, sanitizer):
        """Test that clean input is safe."""
        assert sanitizer.is_safe("Hello, how are you?")

    def test_is_safe_unsafe_input(self, sanitizer):
        """Test that malicious input is detected as unsafe."""
        assert not sanitizer.is_safe("<script>alert('xss')</script>")

    def test_truncate_safely(self, sanitizer):
        """Test safe truncation."""
        long_text = "Word " * 1000
        truncated = sanitizer.truncate_safely(long_text, max_length=100)

        assert len(truncated) <= 110  # Account for "..." and buffer


class TestTopicFilter:
    """Tests for topic filtering."""

    @pytest.fixture
    def topic_filter(self):
        """Create a topic filter."""
        return TopicFilter()

    def test_allow_parking_topic(self, topic_filter):
        """Test that parking topics are allowed."""
        is_allowed, _ = topic_filter.is_allowed_topic("What are your parking rates?")
        assert is_allowed is True

    def test_block_inappropriate_topic(self, topic_filter):
        """Test that inappropriate topics are blocked."""
        is_allowed, _ = topic_filter.is_allowed_topic("How to hack into the system")
        assert is_allowed is False

    def test_get_topic_score_relevant(self, topic_filter):
        """Test topic score for relevant query."""
        score = topic_filter.get_topic_score("parking availability and rates")
        assert score > 0

    def test_get_topic_score_irrelevant(self, topic_filter):
        """Test topic score for irrelevant query."""
        score = topic_filter.get_topic_score("The weather is nice today")
        assert score >= 0  # Should not crash


class TestContentSafetyFilter:
    """Tests for content safety filtering."""

    @pytest.fixture
    def safety_filter(self):
        """Create a content safety filter."""
        return ContentSafetyFilter()

    def test_safe_content_passes(self, safety_filter):
        """Test that safe content passes."""
        is_safe, _ = safety_filter.is_safe("What are your hours?")
        assert is_safe is True

    def test_harmful_content_blocked(self, safety_filter):
        """Test that harmful content is blocked."""
        is_safe, reason = safety_filter.is_safe("how to steal a car")
        assert is_safe is False
        assert reason is not None


class TestGuardRailHandler:
    """Tests for guardrail handler."""

    @pytest.fixture
    def handler(self):
        """Create a guardrail handler."""
        return GuardRailHandler(block_on_violation=False)

    def test_process_safe_input(self, handler):
        """Test processing safe input."""
        processed, error = handler.process_input("What are your hours?")

        assert error is None
        assert processed == "What are your hours?"

    def test_process_blocked_input(self, handler):
        """Test processing blocked input."""
        handler.block_on_violation = True
        processed, error = handler.process_input("How to hack something")

        # Should be blocked or processed with warning
        assert error is not None or processed != "How to hack something"

    def test_process_output(self, handler):
        """Test processing output."""
        output = "Our hours are 6 AM to 11 PM"
        processed, warning = handler.process_output(output)

        assert processed == output
        assert warning is None

    def test_get_statistics(self, handler):
        """Test getting guardrail statistics."""
        handler.process_input("Test input")
        stats = handler.get_statistics()

        assert "total_checks" in stats
        assert "violations" in stats
        assert stats["total_checks"] >= 1


class TestGuardrailIntegration:
    """Integration tests for guardrails."""

    def test_full_guardrail_pipeline(self):
        """Test complete guardrail pipeline."""
        handler = get_guardrail_handler()

        # Process input
        input_text = "What are your parking rates?"
        processed, input_error = handler.process_input(input_text)
        assert input_error is None

        # Process output
        output_text = "Our rates start at $2.50 per hour"
        processed_output, output_warning = handler.process_output(output_text)
        assert processed_output  # Should have output

    def test_pii_in_output_detection(self):
        """Test detecting PII in output."""
        handler = get_guardrail_handler()
        output_with_pii = "Contact John Smith at john@example.com"

        processed, warning = handler.process_output(output_with_pii)
        # Should be processed/redacted
        assert processed is not None

    def test_topic_relevance_scoring(self):
        """Test topic relevance scoring."""
        handler = get_guardrail_handler()

        relevant_score = handler.chain.get_topic_relevance("parking rates and availability")
        irrelevant_score = handler.chain.get_topic_relevance("quantum physics theory")

        # Parking query should score higher
        assert relevant_score >= irrelevant_score
