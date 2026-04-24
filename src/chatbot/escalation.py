"""Escalation system for routing reservation requests to human administrators."""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from src.data.reservation_manager import get_reservation_manager
from src.data.reservation_state import ReservationRequest, CommunicationChannel, ReservationStatus
from src.chatbot.channels import get_channel_handler, MockChannelHandler


class EscalationManager:
    """Manages escalation of reservation requests to administrators."""

    def __init__(
        self,
        default_channel: CommunicationChannel = CommunicationChannel.MOCK,
        admin_contact: Optional[str] = None,
        auto_escalate: bool = True,
    ):
        """
        Initialize the escalation manager.

        Args:
            default_channel: Default communication channel
            admin_contact: Default admin contact (email, webhook URL, etc.)
            auto_escalate: Whether to automatically escalate new reservation requests
        """
        self.reservation_manager = get_reservation_manager()
        self.default_channel = default_channel
        self.admin_contact = admin_contact
        self.auto_escalate = auto_escalate

        # Channel handlers cache
        self.channel_handlers: Dict[CommunicationChannel, Any] = {}

    def get_channel_handler(self, channel: CommunicationChannel):
        """Get or create a channel handler."""
        if channel not in self.channel_handlers:
            self.channel_handlers[channel] = get_channel_handler(channel)
        return self.channel_handlers[channel]

    def escalate_reservation(
        self,
        user_name: str,
        user_surname: str,
        car_number: str,
        start_time: datetime,
        end_time: datetime,
        space_type: str,
        contact_info: str,
        channel: Optional[CommunicationChannel] = None,
        admin_contact: Optional[str] = None,
        expiration_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Escalate a reservation request to the administrator.

        Args:
            user_name: User's first name
            user_surname: User's last name
            car_number: License plate number
            start_time: Reservation start time
            end_time: Reservation end time
            space_type: Type of parking space
            contact_info: User's contact information
            channel: Communication channel (uses default if not specified)
            admin_contact: Admin contact info (uses default if not specified)
            expiration_hours: Hours until request expires

        Returns:
            Dictionary with success status, reservation_id, and details
        """
        try:
            # Use defaults if not specified
            comm_channel = channel or self.default_channel
            admin = admin_contact or self.admin_contact

            # Create reservation request
            reservation = self.reservation_manager.create_reservation_request(
                user_name=user_name,
                user_surname=user_surname,
                car_number=car_number,
                start_time=start_time,
                end_time=end_time,
                space_type=space_type,
                contact_info=contact_info,
                communication_channel=comm_channel,
                expiration_hours=expiration_hours,
            )

            # Get channel handler and send notification
            handler = self.get_channel_handler(comm_channel)
            result = handler.send_request(reservation, admin or "admin@example.com")

            # Update message ID in database
            if result.get("success"):
                self.reservation_manager.set_message_id(
                    reservation.reservation_id,
                    result["message_id"],
                )

                return {
                    "success": True,
                    "reservation_id": reservation.reservation_id,
                    "status": "pending",
                    "message": "Reservation request sent to administrator for approval",
                    "message_id": result["message_id"],
                    "channel": comm_channel.value,
                    "expiration_time": reservation.expiration_time.isoformat() if reservation.expiration_time else None,
                    "estimated_response_time": f"{expiration_hours} hours",
                }
            else:
                # Sending failed - clean up the reservation
                self.reservation_manager.cancel_reservation(reservation.reservation_id)

                return {
                    "success": False,
                    "error": "Failed to send notification to administrator",
                    "details": result.get("error"),
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error escalating reservation: {str(e)}",
            }

    def check_reservation_status(self, reservation_id: str) -> Dict[str, Any]:
        """
        Check the status of a reservation request.

        Args:
            reservation_id: The reservation ID

        Returns:
            Dictionary with status and details
        """
        try:
            reservation = self.reservation_manager.get_reservation(reservation_id)

            if not reservation:
                return {
                    "success": False,
                    "error": f"Reservation {reservation_id} not found",
                }

            return {
                "success": True,
                "reservation_id": reservation.reservation_id,
                "status": reservation.status.value,
                "can_be_approved": reservation.can_be_approved(),
                "is_expired": reservation.is_expired(),
                "created_at": reservation.created_at.isoformat(),
                "updated_at": reservation.updated_at.isoformat(),
                "expiration_time": reservation.expiration_time.isoformat() if reservation.expiration_time else None,
                "admin_note": reservation.admin_note,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error checking reservation status: {str(e)}",
            }

    def get_user_reservations(
        self,
        user_name: str,
        user_surname: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all reservations for a user.

        Args:
            user_name: User's first name
            user_surname: User's last name (optional)

        Returns:
            List of reservation dictionaries
        """
        try:
            reservations = self.reservation_manager.get_reservations_by_user(
                user_name,
                user_surname,
            )

            return [r.to_dict() for r in reservations]

        except Exception as e:
            return []

    def process_admin_response(
        self,
        response: str,
    ) -> Dict[str, Any]:
        """
        Process an administrator's response and update the reservation.

        Args:
            response: Admin response (e.g., "APPROVE abc-123", "REJECT abc-123 Reason")

        Returns:
            Dictionary with result
        """
        try:
            from src.chatbot.admin_agent_final import get_admin_agent

            admin_agent = get_admin_agent()
            result = admin_agent.handle_admin_response(response)

            # If approved/rejected, trigger user notification
            if result.get("success") and result.get("action") in ["approved", "rejected"]:
                reservation_data = result.get("reservation")
                if reservation_data:
                    # In production, send notification to user
                    # For now, just log
                    action = result["action"]
                    print(f"\n🔔 User Notification: Reservation {reservation_data['reservation_id']} was {action}")

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error processing admin response: {str(e)}",
            }

    def get_pending_reservations(self) -> List[Dict[str, Any]]:
        """
        Get all pending reservations.

        Returns:
            List of pending reservation dictionaries
        """
        try:
            reservations = self.reservation_manager.get_pending_reservations()
            return [r.to_dict() for r in reservations]

        except Exception as e:
            return []

    def cleanup_expired(self) -> int:
        """
        Clean up expired reservations.

        Returns:
            Number of reservations marked as expired
        """
        try:
            return self.reservation_manager.cleanup_expired_reservations()

        except Exception as e:
            return 0


class UserFacingEscalationService:
    """Service that provides user-friendly responses about escalation."""

    def __init__(self, escalation_manager: Optional[EscalationManager] = None):
        """Initialize the service."""
        self.escalation_manager = escalation_manager or EscalationManager()

    def submit_reservation_request(
        self,
        user_name: str,
        user_surname: str,
        car_number: str,
        start_time: datetime,
        end_time: datetime,
        space_type: str,
        contact_info: str,
    ) -> str:
        """
        Submit a reservation request from the user (user-facing interface).

        Args:
            user_name: User's first name
            user_surname: User's last name
            car_number: License plate number
            start_time: Reservation start time
            end_time: Reservation end time
            space_type: Type of parking space
            contact_info: User's contact information

        Returns:
            User-friendly message
        """
        result = self.escalation_manager.escalate_reservation(
            user_name=user_name,
            user_surname=user_surname,
            car_number=car_number,
            start_time=start_time,
            end_time=end_time,
            space_type=space_type,
            contact_info=contact_info,
        )

        if result["success"]:
            return f"""✅ Your reservation request has been submitted successfully!

📋 Request ID: {result['reservation_id']}
⏰ Status: Pending Administrator Approval
⏱️ Estimated Response Time: {result.get('estimated_response_time', '24 hours')}

You will receive a notification once your request is reviewed.

To check the status of your request, please use the Request ID: {result['reservation_id']}
"""
        else:
            return f"""❌ Failed to submit your reservation request.

Error: {result.get('error', 'Unknown error')}

Please try again later or contact our support team for assistance.
"""

    def check_status(self, reservation_id: str) -> str:
        """
        Check reservation status (user-facing interface).

        Args:
            reservation_id: The reservation ID

        Returns:
            User-friendly status message
        """
        result = self.escalation_manager.check_reservation_status(reservation_id)

        if not result["success"]:
            return f"""❌ Reservation Not Found

The reservation ID '{reservation_id}' was not found in our system.
Please verify the ID and try again.
"""

        status = result["status"]
        reservation_id = result["reservation_id"]

        status_messages = {
            "pending": "⏳ Your reservation request is pending administrator approval.",
            "approved": "✅ Your reservation has been approved!",
            "rejected": f"❌ Your reservation has been rejected.\n\n{result.get('admin_note', 'No reason provided.')}",
            "cancelled": "🚫 Your reservation has been cancelled.",
            "expired": "⌛ Your reservation request has expired. Please submit a new request.",
        }

        message = status_messages.get(
            status,
            f"Status: {status.upper()}"
        )

        return f"""📋 Reservation Status: {reservation_id}

{message}

Last Updated: {result.get('updated_at', 'N/A')}
"""


# Global instances
_escalation_manager: Optional[EscalationManager] = None
_user_escalation_service: Optional[UserFacingEscalationService] = None


def get_escalation_manager() -> EscalationManager:
    """Get or create the global escalation manager instance."""
    global _escalation_manager
    if _escalation_manager is None:
        _escalation_manager = EscalationManager()
    return _escalation_manager


def get_user_escalation_service() -> UserFacingEscalationService:
    """Get or create the global user-facing escalation service instance."""
    global _user_escalation_service
    if _user_escalation_service is None:
        _user_escalation_service = UserFacingEscalationService()
    return _user_escalation_service
