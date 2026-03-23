"""Tools for the LangGraph-based chatbot agent."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from src.data.dynamic_data import get_db_manager
from src.data.schemas import ParkingSpace, Availability, PricingInfo
from src.data.static_data import get_static_loader


class ParkingTools:
    """Collection of tools for parking-related operations."""

    def __init__(self):
        """Initialize parking tools."""
        self.db_manager = get_db_manager()
        self.static_loader = get_static_loader()

    def get_parking_info(self, topic: str) -> str:
        """
        Get general parking information from knowledge base.

        Args:
            topic: Topic to retrieve (e.g., "location", "hours", "rules")

        Returns:
            Information string.
        """
        content = self.static_loader.load_markdown()

        # Simple section extraction
        lines = content.split("\n")
        result_lines = []
        in_section = False

        topic_lower = topic.lower()

        for i, line in enumerate(lines):
            if line.startswith(f"## ") and topic_lower in line.lower():
                in_section = True
                continue
            elif line.startswith("## "):
                if in_section:
                    break
            elif in_section:
                result_lines.append(line)

        if result_lines:
            return "\n".join(result_lines).strip()

        # Fallback to keyword search
        for i, line in enumerate(lines):
            if topic_lower in line.lower():
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 10)
                return "\n".join(lines[context_start:context_end])

        return f"Sorry, I couldn't find specific information about '{topic}'."

    def check_availability(self, space_type: str = "standard") -> str:
        """
        Check current parking space availability.

        Args:
            space_type: Type of parking space to check

        Returns:
            Availability information string.
        """
        availability = self.db_manager.get_availability(space_type)

        if availability:
            percentage = availability.utilization_percentage
            status = "High availability" if availability.available_spaces > 10 else \
                     "Limited availability" if availability.available_spaces > 3 else \
                     "Very limited availability"

            return (
                f"{space_type.capitalize()} Spaces: "
                f"{availability.available_spaces} available out of {availability.total_spaces} "
                f"({100-percentage:.1f}% available)\n"
                f"Status: {status}"
            )
        else:
            return f"Sorry, I couldn't find availability information for '{space_type}' spaces."

    def get_all_availability(self) -> str:
        """Get availability for all space types."""
        availabilities = self.db_manager.get_all_availabilities()

        if not availabilities:
            return "Availability information is currently unavailable."

        result = "Current Parking Availability:\n\n"
        for avail in availabilities:
            percentage = avail.utilization_percentage
            result += (
                f"{avail.space_type.capitalize()}: "
                f"{avail.available_spaces}/{avail.total_spaces} available "
                f"({100-percentage:.1f}%)\n"
            )

        return result.strip()

    def get_prices(self, space_type: Optional[str] = None) -> str:
        """
        Get pricing information.

        Args:
            space_type: Specific space type or all if None

        Returns:
            Pricing information string.
        """
        if space_type:
            pricing = self.db_manager.get_pricing(space_type)
            if pricing:
                result = f"{pricing.space_type.capitalize()} Pricing:\n"
                result += f"  Hourly Rate: ${pricing.hourly_rate:.2f}\n"
                if pricing.daily_rate:
                    result += f"  Daily Maximum: ${pricing.daily_rate:.2f}\n"
                return result
            else:
                return f"No pricing information found for '{space_type}' spaces."
        else:
            # Get all pricing
            all_pricing = self.db_manager.get_all_pricing()
            result = "Parking Rates:\n\n"
            for pricing in all_pricing:
                result += f"{pricing.space_type.capitalize()}:\n"
                result += f"  Hourly: ${pricing.hourly_rate:.2f}\n"
                if pricing.daily_rate:
                    result += f"  Daily Max: ${pricing.daily_rate:.2f}\n"
                result += "\n"

            # Add weekly pass info
            result += "Weekly and monthly passes are also available. "
            result += "Please contact customer service for details."

            return result.strip()

    def get_location_info(self) -> str:
        """Get parking facility location information."""
        info = self.static_loader.get_location_info()
        return (
            f"{info['name']}\n"
            f"{info['address']}\n"
            f"{info['city']}, {info['state']} {info['postal_code']}\n"
            f"Total Spaces: {info['total_spaces']}"
        )

    def get_working_hours(self) -> str:
        """Get facility working hours."""
        hours = self.static_loader.get_working_hours()
        return (
            "Working Hours:\n"
            f"  Monday - Friday: {hours['monday_friday']}\n"
            f"  Saturday: {hours['saturday']}\n"
            f"  Sunday: {hours['sunday']}\n\n"
            f"Note: {hours['access']}"
        )

    def get_payment_methods(self) -> str:
        """Get accepted payment methods."""
        methods = self.static_loader.get_payment_methods()
        return "Accepted Payment Methods:\n" + "\n".join(f"  • {m}" for m in methods)

    def get_rules_summary(self) -> str:
        """Get parking rules summary."""
        return self.static_loader.get_rules_summary()


class ReservationDataCollector:
    """Collects reservation data from users interactively."""

    def __init__(self):
        """Initialize reservation data collector."""
        self.reset()

    def reset(self) -> None:
        """Reset collected data."""
        self.collected_data = {
            "name": None,
            "surname": None,
            "car_number": None,
            "space_type": None,
            "start_time": None,
            "end_time": None,
            "email": None,
            "phone": None,
        }
        self.current_step = 0
        self.steps = ["name", "surname", "car_number", "space_type", "start_time", "end_time", "contact"]

    def get_current_prompt(self) -> str:
        """Get the prompt for the current collection step."""
        prompts = {
            "name": "To make a reservation, I'll need some information. What's your first name?",
            "surname": "Thank you! What's your last name?",
            "car_number": "Great! What's your license plate number?",
            "space_type": "What type of parking space do you prefer? (standard, compact, ev_charging, accessible, covered, or motorcycle)",
            "start_time": "When would you like to start? Please provide the date and time (e.g., '2026-03-25 10:00 AM').",
            "end_time": "When will you be leaving? Please provide the date and time.",
            "contact": "Finally, how can we contact you? Please provide either an email address or phone number.",
            "complete": None,
        }

        return prompts.get(self.steps[self.current_step], "I need some information to complete your reservation.")

    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input for current step.

        Returns:
            Dict with 'status' ('collecting', 'complete', 'error') and 'message'.
        """
        if self.current_step >= len(self.steps):
            return {"status": "complete", "message": self._get_summary()}

        step = self.steps[self.current_step]
        result = self._validate_and_store(step, user_input)

        if result.get("error"):
            return {"status": "error", "message": result["error"]}

        # Move to next step
        self.current_step += 1

        if self.current_step >= len(self.steps):
            return {"status": "complete", "message": self._get_summary()}

        return {
            "status": "collecting",
            "message": self.get_current_prompt(),
            "collected": self.get_collected_summary(),
        }

    def _validate_and_store(self, step: str, value: str) -> Dict[str, Any]:
        """Validate and store input for a step."""
        value = value.strip()

        if not value:
            return {"error": "This field is required."}

        if step == "name":
            if len(value) < 2 or len(value) > 50:
                return {"error": "Name should be between 2 and 50 characters."}
            self.collected_data["name"] = value

        elif step == "surname":
            if len(value) < 2 or len(value) > 50:
                return {"error": "Surname should be between 2 and 50 characters."}
            self.collected_data["surname"] = value

        elif step == "car_number":
            if len(value) < 2 or len(value) > 20:
                return {"error": "License plate number should be between 2 and 20 characters."}
            self.collected_data["car_number"] = value.upper()

        elif step == "space_type":
            valid_types = ["standard", "compact", "ev_charging", "accessible", "covered", "motorcycle"]
            if value.lower() not in valid_types:
                return {"error": f"Invalid space type. Please choose from: {', '.join(valid_types)}"}
            self.collected_data["space_type"] = value.lower()

        elif step in ["start_time", "end_time"]:
            try:
                # Try common date formats
                for fmt in ["%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%m/%d/%Y %I:%M %p"]:
                    try:
                        parsed_time = datetime.strptime(value, fmt)
                        # Ensure future date
                        if parsed_time < datetime.now():
                            return {"error": "Please provide a future date and time."}
                        self.collected_data[step] = parsed_time
                        break
                    except ValueError:
                        continue
                else:
                    return {"error": "Invalid date format. Please use format like '2026-03-25 10:00 AM'"}

                # Validate end time is after start time
                if step == "end_time" and self.collected_data.get("start_time"):
                    if self.collected_data["end_time"] <= self.collected_data["start_time"]:
                        return {"error": "End time must be after start time."}

            except Exception as e:
                return {"error": f"Invalid date/time: {str(e)}"}

        elif step == "contact":
            # Simple validation for email or phone
            is_email = "@" in value and "." in value
            is_phone = any(c.isdigit() for c in value) and len(value) >= 10

            if not (is_email or is_phone):
                return {"error": "Please provide a valid email address or phone number."}

            if is_email:
                self.collected_data["email"] = value
            else:
                self.collected_data["phone"] = value

        return {}

    def get_collected_summary(self) -> str:
        """Get summary of collected data so far."""
        collected = []
        for key, value in self.collected_data.items():
            if value and key != "email" and key != "phone":
                collected.append(f"{key.replace('_', ' ').title()}: {value}")
            elif key == "email" and value:
                collected.append("Email: provided")
            elif key == "phone" and value:
                collected.append("Phone: provided")

        return " | ".join(collected) if collected else "No data collected yet."

    def _get_summary(self) -> str:
        """Get complete summary for confirmation."""
        summary = (
            f"Reservation Summary:\n"
            f"  Name: {self.collected_data['name']} {self.collected_data['surname']}\n"
            f"  License Plate: {self.collected_data['car_number']}\n"
            f"  Space Type: {self.collected_data['space_type']}\n"
            f"  Start: {self.collected_data['start_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
            f"  End: {self.collected_data['end_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
            f"  Contact: {'Provided' if (self.collected_data['email'] or self.collected_data['phone']) else 'Not provided'}\n\n"
            f"Your reservation has been submitted and is pending confirmation from our staff. "
            f"You will receive a confirmation email or call shortly."
        )
        return summary

    def submit_reservation(self) -> Optional[str]:
        """Submit the reservation to the database."""
        if not all([
            self.collected_data["name"],
            self.collected_data["surname"],
            self.collected_data["car_number"],
            self.collected_data["space_type"],
            self.collected_data["start_time"],
            self.collected_data["end_time"],
        ]):
            return None

        reservation_id = self.db_manager.create_reservation(
            name=self.collected_data["name"],
            surname=self.collected_data["surname"],
            car_number=self.collected_data["car_number"],
            space_type=self.collected_data["space_type"],
            start_time=self.collected_data["start_time"],
            end_time=self.collected_data["end_time"],
            email=self.collected_data.get("email"),
            phone=self.collected_data.get("phone"),
        )

        return reservation_id


# Global instances
_parking_tools: Optional[ParkingTools] = None


def get_parking_tools() -> ParkingTools:
    """Get global parking tools instance."""
    global _parking_tools
    if _parking_tools is None:
        _parking_tools = ParkingTools()
    return _parking_tools
