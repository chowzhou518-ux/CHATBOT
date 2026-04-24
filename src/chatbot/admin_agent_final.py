"""Final working LangChain 1.0 Admin Agent."""

import re
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from src.data.reservation_manager import get_reservation_manager


class FinalLangChainAdminAgent:
    """Final working version using LangChain 1.0."""

    def __init__(self, debug=False):
        from src.core.llm_handler import get_llm_handler

        self.llm_handler = get_llm_handler()
        self.reservation_manager = get_reservation_manager()

        self.llm = ChatOpenAI(
            model=self.llm_handler.model,
            api_key=self.llm_handler.api_key,
            base_url=self.llm_handler.base_url,
            temperature=0.7,
        )

        self.tools = self._create_tools()
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt="You are a parking admin assistant. Use tools to help administrators.",
            debug=debug,
        )

    def _create_tools(self):
        @tool
        def list_pending() -> str:
            """List all pending reservation requests."""
            reservations = self.reservation_manager.get_pending_reservations()
            if not reservations:
                return "No pending reservations."
            result = [f"Pending reservations ({len(reservations)}):"]
            for i, res in enumerate(reservations, 1):
                result.append(f"{i}. {res.reservation_id} - {res.user_name} {res.user_surname} - {res.car_number}")
            return "\n".join(result)

        @tool
        def get_stats() -> str:
            """Get reservation statistics."""
            stats = self.reservation_manager.get_statistics()
            return f"Total: {stats['total']}, Pending: {stats['pending']}, Approved: {stats['approved']}"

        @tool
        def approve_res(reservation_id: str) -> str:
            """Approve a parking reservation by ID."""
            reservation = self.reservation_manager.approve_reservation(reservation_id)
            if reservation:
                return f"Approved {reservation_id} for {reservation.user_name} {reservation.user_surname}"
            return f"Reservation {reservation_id} not found"

        @tool
        def reject_res(reservation_id: str, reason: str) -> str:
            """Reject a parking reservation by ID with reason."""
            reservation = self.reservation_manager.reject_reservation(reservation_id, admin_note=reason)
            if reservation:
                return f"Rejected {reservation_id}: {reason}"
            return f"Reservation {reservation_id} not found"

        return [list_pending, get_stats, approve_res, reject_res]

    def process_message(self, message: str) -> str:
        # Fast path for simple commands
        message_lower = message.lower().strip()
        if message_lower in ["list", "pending"]:
            return self.tools[0].func()
        if message_lower in ["stats", "statistics"]:
            return self.tools[1].func()

        approve_match = re.match(r'^approve\s+(\S+)', message, re.IGNORECASE)
        if approve_match:
            return self.tools[2].func(approve_match.group(1))

        reject_match = re.match(r'^reject\s+(\S+)\s+(.+)', message, re.IGNORECASE)
        if reject_match:
            return self.tools[3].func(reject_match.group(1), reject_match.group(2))

        # Use LangChain agent for natural language
        try:
            response = self.agent.invoke({"messages": [("user", message)]})
            return response["messages"][-1].content
        except Exception as e:
            return f"Error: {str(e)}\nTry: list, stats, approve <id>, reject <id> <reason>"

    def handle_admin_response(self, response: str) -> dict:
        """Handle administrator response for escalation integration.

        Args:
            response: Admin response (e.g., "APPROVE abc-123", "REJECT abc-123 Reason")

        Returns:
            Dictionary with action result
        """
        import re
        from src.data.reservation_state import ReservationStatus

        response = response.strip()

        # Parse APPROVE command
        approve_match = re.match(r'^APPROVE\s+(\S+)(?:\s+(.+))?$', response, re.IGNORECASE)
        if approve_match:
            reservation_id = approve_match.group(1)
            note = approve_match.group(2) or ""

            reservation = self.reservation_manager.approve_reservation(reservation_id, admin_note=note)
            if reservation:
                return {
                    "success": True,
                    "action": "approved",
                    "reservation": reservation.to_dict(),
                    "message": f"Reservation {reservation_id} approved successfully",
                }
            else:
                return {
                    "success": False,
                    "action": "approve_failed",
                    "error": f"Reservation {reservation_id} not found",
                }

        # Parse REJECT command
        reject_match = re.match(r'^REJECT\s+(\S+)(?:\s+(.+))?$', response, re.IGNORECASE)
        if reject_match:
            reservation_id = reject_match.group(1)
            reason = reject_match.group(2) or "No reason provided"

            reservation = self.reservation_manager.reject_reservation(reservation_id, admin_note=reason)
            if reservation:
                return {
                    "success": True,
                    "action": "rejected",
                    "reservation": reservation.to_dict(),
                    "message": f"Reservation {reservation_id} rejected",
                }
            else:
                return {
                    "success": False,
                    "action": "reject_failed",
                    "error": f"Reservation {reservation_id} not found",
                }

        # Unknown command
        return {
            "success": False,
            "action": "unknown",
            "error": "Could not parse response. Use: APPROVE <id> [note] or REJECT <id> [reason]",
        }


# Global instance
_final_agent = None


def get_final_admin_agent():
    global _final_agent
    if _final_agent is None:
        _final_agent = FinalLangChainAdminAgent()
    return _final_agent


def get_admin_agent():
    return get_final_admin_agent()
