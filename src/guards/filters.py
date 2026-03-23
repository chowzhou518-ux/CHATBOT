"""PII detection and filtering for data protection."""

import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import RecognizerResult, OperatorConfig

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    print("Warning: Presidio not available. Using regex-based PII detection.")


class PIIType(str, Enum):
    """Types of PII to detect."""
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    LICENSE_PLATE = "LICENSE_PLATE"
    CREDIT_CARD = "CREDIT_CARD"
    SSN = "SSN"
    IP_ADDRESS = "IP_ADDRESS"
    LOCATION = "LOCATION"


@dataclass
class PIIEntity:
    """Detected PII entity."""
    entity_type: PIIType
    text: str
    start: int
    end: int
    confidence: float


class PIIDetector:
    """Detector for Personally Identifiable Information."""

    def __init__(self, use_presidio: bool = True):
        """Initialize PII detector."""
        self.use_presidio = use_presidio and PRESIDIO_AVAILABLE

        if self.use_presidio:
            self.analyzer = AnalyzerEngine()
        else:
            self._compile_regex_patterns()

    def _compile_regex_patterns(self) -> None:
        """Compile regex patterns for PII detection."""
        self.patterns = {
            PIIType.EMAIL: re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            PIIType.PHONE: re.compile(
                r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ),
            PIIType.LICENSE_PLATE: re.compile(
                r'\b[A-Z]{1,4}[-\s]?\d{1,4}[A-Z]{0,3}\b|\b\d{1,4}[-\s]?[A-Z]{1,3}[-\s]?\d{1,4}\b'
            ),
            PIIType.CREDIT_CARD: re.compile(
                r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
            ),
            PIIType.SSN: re.compile(
                r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b'
            ),
            PIIType.IP_ADDRESS: re.compile(
                r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
            ),
        }

    def detect_pii(self, text: str) -> List[PIIEntity]:
        """
        Detect PII in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected PII entities.
        """
        if self.use_presidio:
            return self._detect_with_presidio(text)
        else:
            return self._detect_with_regex(text)

    def _detect_with_presidio(self, text: str) -> List[PIIEntity]:
        """Detect PII using Presidio."""
        entities = []

        try:
            results = self.analyzer.analyze(
                text=text,
                language='en',
                entities=[
                    "PERSON",
                    "EMAIL_ADDRESS",
                    "PHONE_NUMBER",
                    "CREDIT_CARD",
                    "US_SSN",
                    "IP_ADDRESS",
                    "LOCATION",
                ],
            )

            for result in results:
                entity_type = self._map_presidio_type(result.entity_type)
                entities.append(PIIEntity(
                    entity_type=entity_type,
                    text=text[result.start:result.end],
                    start=result.start,
                    end=result.end,
                    confidence=result.score,
                ))

        except Exception as e:
            print(f"Presidio detection error: {e}. Falling back to regex.")
            return self._detect_with_regex(text)

        return entities

    def _detect_with_regex(self, text: str) -> List[PIIEntity]:
        """Detect PII using regex patterns."""
        entities = []

        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                entities.append(PIIEntity(
                    entity_type=pii_type,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,  # Fixed confidence for regex
                ))

        return entities

    def _map_presidio_type(self, presidio_type: str) -> PIIType:
        """Map Presidio entity type to our PIIType enum."""
        mapping = {
            "PERSON": PIIType.PERSON,
            "EMAIL_ADDRESS": PIIType.EMAIL,
            "PHONE_NUMBER": PIIType.PHONE,
            "CREDIT_CARD": PIIType.CREDIT_CARD,
            "US_SSN": PIIType.SSN,
            "IP_ADDRESS": PIIType.IP_ADDRESS,
            "LOCATION": PIIType.LOCATION,
        }
        return mapping.get(presidio_type, PIIType.PERSON)


class PIIFilter:
    """Filter and mask PII from text."""

    def __init__(self, detector: Optional[PIIDetector] = None):
        """Initialize PII filter."""
        self.detector = detector or PIIDetector()

        if PRESIDIO_AVAILABLE:
            self.anonymizer = AnonymizerEngine()

    def mask_pii(
        self,
        text: str,
        mask_char: str = "*",
        entity_types: Optional[Set[PIIType]] = None,
    ) -> str:
        """
        Mask PII in text.

        Args:
            text: Text to mask
            mask_char: Character to use for masking
            entity_types: Types of PII to mask (all if None)

        Returns:
            Text with PII masked.
        """
        entities = self.detector.detect_pii(text)

        # Filter by entity type if specified
        if entity_types:
            entities = [e for e in entities if e.entity_type in entity_types]

        # Sort by start position in reverse order to avoid offset issues
        entities.sort(key=lambda x: x.start, reverse=True)

        # Apply masking
        masked_text = text
        for entity in entities:
            masked_text = (
                masked_text[:entity.start] +
                mask_char * (entity.end - entity.start) +
                masked_text[entity.end:]
            )

        return masked_text

    def anonymize_pii(self, text: str) -> str:
        """
        Anonymize PII using Presidio anonymizer.

        Args:
            text: Text to anonymize

        Returns:
            Anonymized text.
        """
        if not PRESIDIO_AVAILABLE:
            return self.mask_pii(text)

        entities = self.detector.detect_pii(text)

        # Convert to Presidio format
        recognizer_results = [
            RecognizerResult(
                entity_type=entity.entity_type.value,
                start=entity.start,
                end=entity.end,
                score=entity.confidence,
            )
            for entity in entities
        ]

        try:
            result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=recognizer_results,
            )
            return result.text
        except Exception as e:
            print(f"Anonymization error: {e}. Falling back to masking.")
            return self.mask_pii(text)

    def redact_pii(self, text: str) -> str:
        """
        Redact PII with placeholders.

        Args:
            text: Text to redact

        Returns:
            Text with PII replaced with placeholders.
        """
        entities = self.detector.detect_pii(text)

        redacted_text = text
        # Sort by start position in reverse order
        entities.sort(key=lambda x: x.start, reverse=True)

        placeholders = {
            PIIType.PERSON: "[NAME]",
            PIIType.EMAIL: "[EMAIL]",
            PIIType.PHONE: "[PHONE]",
            PIIType.LICENSE_PLATE: "[LICENSE_PLATE]",
            PIIType.CREDIT_CARD: "[CREDIT_CARD]",
            PIIType.SSN: "[SSN]",
            PIIType.IP_ADDRESS: "[IP_ADDRESS]",
            PIIType.LOCATION: "[LOCATION]",
        }

        for entity in entities:
            placeholder = placeholders.get(entity.entity_type, "[REDACTED]")
            redacted_text = (
                redacted_text[:entity.start] +
                placeholder +
                redacted_text[entity.end:]
            )

        return redacted_text

    def contains_pii(
        self,
        text: str,
        entity_types: Optional[Set[PIIType]] = None,
    ) -> bool:
        """
        Check if text contains PII.

        Args:
            text: Text to check
            entity_types: Types of PII to check for (all if None)

        Returns:
            True if PII is detected.
        """
        entities = self.detector.detect_pii(text)

        if entity_types:
            entities = [e for e in entities if e.entity_type in entity_types]

        return len(entities) > 0

    def extract_pii_summary(self, text: str) -> Dict[str, int]:
        """
        Get a summary of PII types found in text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with counts of each PII type.
        """
        entities = self.detector.detect_pii(text)

        summary = {}
        for entity in entities:
            type_name = entity.entity_type.value
            summary[type_name] = summary.get(type_name, 0) + 1

        return summary


class InputSanitizer:
    """Sanitize user input for security."""

    # Patterns that might indicate injection attacks
    INJECTION_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'on\w+\s*=',  # Event handlers (onclick, onload, etc.)
        r'javascript:',  # JavaScript protocol
        r'\$\{.*?\}',  # Template injection
        r'--|\#|;',  # SQL comments (basic)
    ]

    def __init__(self):
        """Compile injection patterns."""
        self.injection_regex = re.compile(
            '|'.join(f'(?:{pattern})' for pattern in self.INJECTION_PATTERNS),
            re.IGNORECASE | re.DOTALL,
        )

    def sanitize(self, text: str) -> str:
        """
        Sanitize input by removing potential injections.

        Args:
            text: Input text

        Returns:
            Sanitized text.
        """
        # Remove script tags and other injections
        sanitized = self.injection_regex.sub('', text)

        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())

        return sanitized.strip()

    def is_safe(self, text: str) -> bool:
        """
        Check if input is safe.

        Args:
            text: Input to check

        Returns:
            True if input appears safe.
        """
        sanitized = self.sanitize(text)
        return sanitized == text

    def truncate_safely(self, text: str, max_length: int = 1000) -> str:
        """
        Truncate text at a safe boundary.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text.
        """
        if len(text) <= max_length:
            return text

        # Try to truncate at a sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')

        # Use the latest sentence ending
        boundary = max(last_period, last_exclamation, last_question)

        if boundary > max_length * 0.8:  # If boundary is in last 20%
            return text[:boundary + 1]

        return truncated + "..."


# Global instances
_pii_detector: Optional[PIIDetector] = None
_pii_filter: Optional[PIIFilter] = None
_input_sanitizer: Optional[InputSanitizer] = None


def get_pii_detector() -> PIIDetector:
    """Get global PII detector instance."""
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector


def get_pii_filter() -> PIIFilter:
    """Get global PII filter instance."""
    global _pii_filter
    if _pii_filter is None:
        _pii_filter = PIIFilter()
    return _pii_filter


def get_input_sanitizer() -> InputSanitizer:
    """Get global input sanitizer instance."""
    global _input_sanitizer
    if _input_sanitizer is None:
        _input_sanitizer = InputSanitizer()
    return _input_sanitizer
