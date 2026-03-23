"""Static data loading and processing for vector database."""

import os
from typing import List, Dict
from pathlib import Path


class StaticDataLoader:
    """Loader for static parking knowledge base."""

    def __init__(self, knowledge_base_path: str = "data/knowledge_base.md"):
        """Initialize the static data loader."""
        self.knowledge_base_path = Path(knowledge_base_path)

    def load_markdown(self) -> str:
        """Load the markdown knowledge base."""
        if not self.knowledge_base_path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self.knowledge_base_path}")

        with open(self.knowledge_base_path, "r", encoding="utf-8") as f:
            return f.read()

    def load_documents(self) -> List[Dict[str, str]]:
        """
        Load knowledge base as structured documents.

        Returns:
            List of documents with metadata.
        """
        content = self.load_markdown()

        # Split into sections based on headers
        documents = []
        current_section = "General"
        current_content = []

        lines = content.split("\n")
        for line in lines:
            if line.startswith("## "):
                # Save previous section
                if current_content:
                    documents.append({
                        "content": "\n".join(current_content).strip(),
                        "metadata": {"section": current_section}
                    })
                # Start new section
                current_section = line[3:].strip()
                current_content = []
            elif line.startswith("# "):
                # Main title, skip
                continue
            else:
                current_content.append(line)

        # Add last section
        if current_content:
            documents.append({
                "content": "\n".join(current_content).strip(),
                "metadata": {"section": current_section}
            })

        return documents

    def get_faq_pairs(self) -> List[Dict[str, str]]:
        """
        Extract FAQ-like pairs from the knowledge base.

        Returns:
            List of Q&A pairs.
        """
        content = self.load_markdown()

        # This is a simplified version - in production, you might want
        # to structure the knowledge base differently
        faqs = [
            {
                "question": "What are your working hours?",
                "answer": self._extract_section(content, "Working Hours"),
            },
            {
                "question": "What are the parking rates?",
                "answer": self._extract_section(content, "Pricing"),
            },
            {
                "question": "Where is the parking located?",
                "answer": self._extract_section(content, "Location"),
            },
            {
                "question": "How do I make a reservation?",
                "answer": self._extract_section(content, "Booking and Reservation Process"),
            },
            {
                "question": "What types of parking spaces are available?",
                "answer": self._extract_section(content, "Parking Space Types"),
            },
        ]

        return faqs

    def _extract_section(self, content: str, section_title: str) -> str:
        """Extract a specific section from the content."""
        lines = content.split("\n")
        section_lines = []
        in_section = False
        found = False

        for line in lines:
            if line.startswith(f"## {section_title}"):
                in_section = True
                found = True
                continue
            elif line.startswith("## "):
                if in_section:
                    break
            elif in_section:
                section_lines.append(line)

        if found:
            return "\n".join(section_lines).strip()
        return f"Information about {section_title} not found."

    def get_summary(self) -> str:
        """Get a brief summary of the parking facility."""
        return """
        CityCenter Parking is a downtown parking facility offering 500 parking spaces
        across multiple types: standard, compact, EV charging, accessible, covered, and motorcycle.
        Located at 123 Main Street, the facility is open 6 AM - 11 PM on weekdays,
        with weekend hours varying. Rates start at $1.50/hour for motorcycles,
        $2.50/hour for compact and accessible spaces, $3.00/hour for standard spaces,
        and up to $4.50/hour for covered spaces. EV charging is available at $4.00/hour.
        Reservations can be made up to 30 days in advance through this chatbot.
        """

    def get_location_info(self) -> Dict[str, str]:
        """Get structured location information."""
        return {
            "name": "CityCenter Parking",
            "address": "123 Main Street, Downtown",
            "city": "Metropolitan City",
            "state": "CA",
            "postal_code": "90210",
            "total_spaces": "500",
        }

    def get_working_hours(self) -> Dict[str, str]:
        """Get working hours information."""
        return {
            "monday_friday": "6:00 AM - 11:00 PM",
            "saturday": "7:00 AM - 12:00 AM (Midnight)",
            "sunday": "8:00 AM - 10:00 PM",
            "access": "24/7 exit for vehicles already parked",
        }

    def get_payment_methods(self) -> List[str]:
        """Get accepted payment methods."""
        return [
            "Credit/Debit Cards (Visa, Mastercard, American Express, Discover)",
            "Mobile Payment (Apple Pay, Google Pay)",
            "Cash (at payment kiosks)",
            "Monthly invoicing for business accounts",
        ]

    def get_rules_summary(self) -> str:
        """Get a summary of parking rules."""
        return """
        Key Rules:
        - Park only within marked lines
        - Display parking receipt visibly
        - Do not block other vehicles or access lanes
        - Turn off engine while parked
        - No overnight parking without reservation
        - 30-minute limit at EV charging stations when others are waiting
        - Free cancellation up to 2 hours before reservation time
        """


def get_static_loader() -> StaticDataLoader:
    """Get the static data loader instance."""
    return StaticDataLoader()
