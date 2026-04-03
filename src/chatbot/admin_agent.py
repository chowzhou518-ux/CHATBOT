"""Administrator agent for handling reservation approvals."""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime

# Note: Using simplified tool approach instead of full LangChain agent
# from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.core.llm_handler import LLMHandler, get_llm_handler
from src.data.reservation_manager import get_reservation_manager
from src.data.reservation_state import ReservationStatus, ReservationRequest


class AdminAgent:
    """Agent for handling administrator interactions and reservation approvals."""

    def __init__(
        self,
        llm_handler: Optional[LLMHandler] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize the admin agent."""
        self.llm_handler = llm_handler or get_llm_handler()
        self.reservation_manager = get_reservation_manager()

        # Admin system prompt
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Available tools
        self.tools = self._create_tools()

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the admin agent."""
        return """You are a Parking Reservation Administrator Assistant. Your role is to help administrators manage parking reservation requests.

**Your Capabilities:**
1. View pending reservation requests
2. Approve or reject reservations
3. Provide details about specific reservations
4. Show statistics about reservations

**Commands:**
- Use the list_pending_reservations tool to see all pending requests
- Use the approve_reservation tool with a reservation ID to approve
- Use the reject_reservation tool with a reservation ID to reject
- Use the get_reservation_details tool to view specific reservation info
- Use the get_statistics tool to see overall statistics

**Important:**
- Always verify the reservation details before approving
- When rejecting, provide a clear reason
- Be helpful and efficient in your responses
- Format responses clearly for the administrator

**Response Format:**
When showing reservation details, use a clear, structured format.
When approving/rejecting, confirm the action and explain what happens next."""

    def _create_tools(self) -> List:
        """Create tools for the admin agent."""

        @tool
        def list_pending_reservations() -> str:
            """List all pending reservation requests that need admin approval."""
            try:
                reservations = self.reservation_manager.get_pending_reservations()

                if not reservations:
                    return "No pending reservations at the moment."

                result = ["📋 Pending Reservation Requests:\n"]

                for i, res in enumerate(reservations, 1):
                    result.append(f"""
{i}. Reservation ID: {res.reservation_id}
   User: {res.user_name} {res.user_surname}
   Car: {res.car_number}
   Space Type: {res.space_type}
   Start: {res.start_time.strftime('%Y-%m-%d %H:%M')}
   End: {res.end_time.strftime('%Y-%m-%d %H:%M')}
   Contact: {res.contact_info}
   Expires: {res.expiration_time.strftime('%Y-%m-%d %H:%M') if res.expiration_time else 'Never'}
""")

                return "\n".join(result)

            except Exception as e:
                return f"Error listing pending reservations: {str(e)}"

        @tool
        def approve_reservation(reservation_id: str, note: str = "") -> str:
            """
            Approve a parking reservation.

            Args:
                reservation_id: The ID of the reservation to approve
                note: Optional note from administrator
            """
            try:
                reservation = self.reservation_manager.approve_reservation(
                    reservation_id,
                    admin_note=note if note else None,
                )

                if not reservation:
                    return f"❌ Reservation {reservation_id} not found."

                return f"""✅ Reservation Approved Successfully!

Reservation ID: {reservation_id}
User: {reservation.user_name} {reservation.user_surname}
Car: {reservation.car_number}
Start: {reservation.start_time.strftime('%Y-%m-%d %H:%M')}
End: {reservation.end_time.strftime('%Y-%m-%d %H:%M')}

{f'Admin Note: {note}' if note else ''}

The user will be notified of this approval.
"""

            except Exception as e:
                return f"❌ Error approving reservation: {str(e)}"

        @tool
        def reject_reservation(reservation_id: str, reason: str = "") -> str:
            """
            Reject a parking reservation.

            Args:
                reservation_id: The ID of the reservation to reject
                reason: Reason for rejection (recommended)
            """
            try:
                if not reason:
                    reason = "No reason provided"

                reservation = self.reservation_manager.reject_reservation(
                    reservation_id,
                    admin_note=reason,
                )

                if not reservation:
                    return f"❌ Reservation {reservation_id} not found."

                return f"""❌ Reservation Rejected

Reservation ID: {reservation_id}
User: {reservation.user_name} {reservation.user_surname}
Reason: {reason}

The user will be notified of this rejection.
"""

            except Exception as e:
                return f"❌ Error rejecting reservation: {str(e)}"

        @tool
        def get_reservation_details(reservation_id: str) -> str:
            """
            Get detailed information about a specific reservation.

            Args:
                reservation_id: The ID of the reservation
            """
            try:
                reservation = self.reservation_manager.get_reservation(reservation_id)

                if not reservation:
                    return f"❌ Reservation {reservation_id} not found."

                return f"""📄 Reservation Details

Reservation ID: {reservation.reservation_id}
Status: {reservation.status.value.upper()}

User Information:
- Name: {reservation.user_name} {reservation.user_surname}
- Contact: {reservation.contact_info}

Reservation Details:
- Car: {reservation.car_number}
- Space Type: {reservation.space_type}
- Start: {reservation.start_time.strftime('%Y-%m-%d %H:%M')}
- End: {reservation.end_time.strftime('%Y-%m-%d %H:%M')}

Timestamps:
- Created: {reservation.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Updated: {reservation.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
- Expires: {reservation.expiration_time.strftime('%Y-%m-%d %H:%M:%S') if reservation.expiration_time else 'Never'}

{f'Admin Note: {reservation.admin_note}' if reservation.admin_note else ''}
"""

            except Exception as e:
                return f"❌ Error getting reservation details: {str(e)}"

        @tool
        def get_statistics() -> str:
            """Get overall reservation statistics."""
            try:
                stats = self.reservation_manager.get_statistics()

                return f"""📊 Reservation Statistics

Total Reservations: {stats['total']}
⏳ Pending: {stats['pending']}
✅ Approved: {stats['approved']}
❌ Rejected: {stats['rejected']}
🚫 Cancelled: {stats['cancelled']}
⌛ Expired: {stats['expired']}

Approval Rate: {(stats['approved'] / stats['total'] * 100) if stats['total'] > 0 else 0:.1f}%
"""

            except Exception as e:
                return f"❌ Error getting statistics: {str(e)}"

        @tool
        def cleanup_expired() -> str:
            """Mark expired reservations as expired (run periodically)."""
            try:
                count = self.reservation_manager.cleanup_expired_reservations()
                return f"✅ Marked {count} reservation(s) as expired."

            except Exception as e:
                return f"❌ Error cleaning up expired reservations: {str(e)}"

        return [
            list_pending_reservations,
            approve_reservation,
            reject_reservation,
            get_reservation_details,
            get_statistics,
            cleanup_expired,
        ]

    def process_message(self, message: str) -> str:
        """
        Process a message from the administrator.

        Args:
            message: The administrator's message

        Returns:
            The agent's response
        """
        try:
            # Simple command parsing for quick actions
            approve_match = re.match(r'^approve\s+(\S+)(?:\s+(.+))?$', message, re.IGNORECASE)
            reject_match = re.match(r'^reject\s+(\S+)(?:\s+(.+))?$', message, re.IGNORECASE)
            details_match = re.match(r'^(?:details?|info|get)\s+(\S+)$', message, re.IGNORECASE)
            stats_match = re.match(r'^(?:stats?|statistics)$', message, re.IGNORECASE)
            list_match = re.match(r'^(?:list|pending|show)(?:\s+pending)?$', message, re.IGNORECASE)

            if approve_match:
                res_id = approve_match.group(1)
                note = approve_match.group(2) or ""
                return self.tools[1].func(res_id, note)

            elif reject_match:
                res_id = reject_match.group(1)
                reason = reject_match.group(2) or ""
                return self.tools[2].func(res_id, reason)

            elif details_match:
                res_id = details_match.group(1)
                return self.tools[3].func(res_id)

            elif stats_match:
                return self.tools[4].func()

            elif list_match:
                return self.tools[0].func()

            # For complex queries, use LLM
            else:
                # Create tool descriptions
                tool_descriptions = "\n".join([
                    f"- {tool.name}: {tool.description}"
                    for tool in self.tools
                ])

                prompt = f"""You are a parking reservation administrator assistant.

Available tools:
{tool_descriptions}

Administrator message: {message}

Use the appropriate tool to handle this request. If no tool is needed, respond helpfully."""

                # In production, use LangChain agent
                # For now, return helpful message
                return """I can help you manage parking reservations. Here are the available commands:

**Quick Commands:**
- `list` or `pending` - Show all pending reservations
- `approve <reservation_id> [note]` - Approve a reservation
- `reject <reservation_id> [reason]` - Reject a reservation
- `details <reservation_id>` - Get reservation details
- `stats` - Show reservation statistics

**Examples:**
- `list`
- `approve abc-123-def Approved for weekend`
- `reject abc-123-def Space already booked`
- `details abc-123-def`
- `stats`

What would you like to do?
"""

        except Exception as e:
            return f"Error processing message: {str(e)}"

    def parse_admin_response(self, response: str) -> Dict[str, Any]:
        """
        Parse administrator's response (from email, API, etc.).

        Args:
            response: The administrator's response text

        Returns:
            Dictionary with action, reservation_id, and note/reason
        """
        response = response.strip()

        # Pattern matching for APPROVE/REJECT commands
        approve_pattern = r'^APPROVE\s+(\S+)(?:\s+(.+))?$'
        reject_pattern = r'^REJECT\s+(\S+)(?:\s+(.+))?$'

        approve_match = re.match(approve_pattern, response, re.IGNORECASE)
        reject_match = re.match(reject_pattern, response, re.IGNORECASE)

        if approve_match:
            return {
                "action": "approve",
                "reservation_id": approve_match.group(1),
                "note": approve_match.group(2) or "",
            }

        elif reject_match:
            return {
                "action": "reject",
                "reservation_id": reject_match.group(1),
                "reason": reject_match.group(2) or "No reason provided",
            }

        else:
            return {
                "action": "unknown",
                "error": f"Could not parse response. Use: APPROVE <id> [note] or REJECT <id> [reason]",
            }

    def handle_admin_response(self, response: str) -> Dict[str, Any]:
        """
        Handle administrator's response and update reservation accordingly.

        Args:
            response: The administrator's response

        Returns:
            Dictionary with success status and result
        """
        parsed = self.parse_admin_response(response)

        if parsed["action"] == "approve":
            reservation = self.reservation_manager.approve_reservation(
                parsed["reservation_id"],
                admin_note=parsed.get("note"),
            )

            if reservation:
                return {
                    "success": True,
                    "action": "approved",
                    "reservation": reservation.to_dict(),
                    "message": f"Reservation {parsed['reservation_id']} approved successfully",
                }
            else:
                return {
                    "success": False,
                    "action": "approve_failed",
                    "error": f"Reservation {parsed['reservation_id']} not found",
                }

        elif parsed["action"] == "reject":
            reservation = self.reservation_manager.reject_reservation(
                parsed["reservation_id"],
                admin_note=parsed.get("reason"),
            )

            if reservation:
                return {
                    "success": True,
                    "action": "rejected",
                    "reservation": reservation.to_dict(),
                    "message": f"Reservation {parsed['reservation_id']} rejected",
                }
            else:
                return {
                    "success": False,
                    "action": "reject_failed",
                    "error": f"Reservation {parsed['reservation_id']} not found",
                }

        else:
            return {
                "success": False,
                "action": "unknown",
                "error": parsed.get("error", "Unknown action"),
            }


# Global instance
_admin_agent: Optional[AdminAgent] = None


def get_admin_agent() -> AdminAgent:
    """Get or create the global admin agent instance."""
    global _admin_agent
    if _admin_agent is None:
        _admin_agent = AdminAgent()
    return _admin_agent
