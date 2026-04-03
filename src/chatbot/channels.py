"""Communication channel handlers for administrator notifications."""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime
import requests

from src.data.reservation_state import ReservationRequest, CommunicationChannel


class CommunicationChannelHandler:
    """Base class for communication channel handlers."""

    def send_request(
        self,
        request: ReservationRequest,
        admin_contact: str,
    ) -> Dict[str, Any]:
        """
        Send reservation request to administrator.

        Args:
            request: The reservation request
            admin_contact: Admin's contact (email, phone, webhook URL)

        Returns:
            Dictionary with success status and message_id
        """
        raise NotImplementedError("Subclasses must implement send_request")

    def format_request_message(self, request: ReservationRequest) -> str:
        """Format the reservation request into a human-readable message."""
        return f"""
Parking Reservation Request

Request ID: {request.reservation_id}
User: {request.user_name} {request.user_surname}
Car: {request.car_number}
Space Type: {request.space_type}

Start: {request.start_time.strftime('%Y-%m-%d %H:%M')}
End: {request.end_time.strftime('%Y-%m-%d %H:%M')}

Contact: {request.contact_info}
Created: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}

To approve this reservation, please respond with:
APPROVE {request.reservation_id}

To reject this reservation, please respond with:
REJECT {request.reservation_id} [optional reason]

This request will expire on: {request.expiration_time.strftime('%Y-%m-%d %H:%M:%S') if request.expiration_time else 'Never'}
"""


class EmailChannelHandler(CommunicationChannelHandler):
    """Handler for email notifications."""

    def __init__(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
    ):
        """Initialize email handler."""
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("FROM_EMAIL", self.smtp_username)

    def send_request(
        self,
        request: ReservationRequest,
        admin_contact: str,
    ) -> Dict[str, Any]:
        """
        Send reservation request via email.

        Args:
            request: The reservation request
            admin_contact: Admin's email address

        Returns:
            Dictionary with success status and message_id
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"🚗 Parking Reservation Request - {request.user_name} {request.user_surname}"
            message["From"] = self.from_email
            message["To"] = admin_contact

            # Create HTML and plain text versions
            text_content = self.format_request_message(request)
            html_content = self._format_html_message(request)

            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")

            message.attach(part1)
            message.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

            # Generate message ID (in production, get from email server)
            message_id = f"email_{request.reservation_id}_{datetime.utcnow().timestamp()}"

            return {
                "success": True,
                "message_id": message_id,
                "channel": "email",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "channel": "email",
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _format_html_message(self, request: ReservationRequest) -> str:
        """Format the reservation request as HTML email."""
        return f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">🚗 Parking Reservation Request</h2>

        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Request ID:</strong> {request.reservation_id}</p>
            <p><strong>User:</strong> {request.user_name} {request.user_surname}</p>
            <p><strong>Car:</strong> {request.car_number}</p>
            <p><strong>Space Type:</strong> {request.space_type}</p>
            <p><strong>Start:</strong> {request.start_time.strftime('%Y-%m-%d %H:%M')}</p>
            <p><strong>End:</strong> {request.end_time.strftime('%Y-%m-%d %H:%M')}</p>
            <p><strong>Contact:</strong> {request.contact_info}</p>
        </div>

        <h3>Actions:</h3>
        <div style="margin: 20px 0;">
            <p style="margin: 10px 0;">
                <a href="mailto:?subject=APPROVE&body=APPROVE {request.reservation_id}"
                   style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    ✓ Approve
                </a>
            </p>
            <p style="margin: 10px 0;">
                <a href="mailto:?subject=REJECT&body=REJECT {request.reservation_id}"
                   style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    ✗ Reject
                </a>
            </p>
        </div>

        <p style="color: #666; font-size: 12px;">
            Expires: {request.expiration_time.strftime('%Y-%m-%d %H:%M:%S') if request.expiration_time else 'Never'}
        </p>
    </div>
</body>
</html>
"""


class RestAPIChannelHandler(CommunicationChannelHandler):
    """Handler for REST API notifications (webhook)."""

    def __init__(self, api_endpoint: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize REST API handler."""
        self.api_endpoint = api_endpoint or os.getenv("ADMIN_API_ENDPOINT")
        self.api_key = api_key or os.getenv("ADMIN_API_KEY")

    def send_request(
        self,
        request: ReservationRequest,
        admin_contact: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send reservation request via REST API/webhook.

        Args:
            request: The reservation request
            admin_contact: Not used for REST API (uses configured endpoint)

        Returns:
            Dictionary with success status and message_id
        """
        try:
            if not self.api_endpoint:
                return {
                    "success": False,
                    "error": "API endpoint not configured",
                    "channel": "rest_api",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # Prepare payload
            payload = {
                "reservation_id": request.reservation_id,
                "user_name": request.user_name,
                "user_surname": request.user_surname,
                "car_number": request.car_number,
                "space_type": request.space_type,
                "start_time": request.start_time.isoformat(),
                "end_time": request.end_time.isoformat(),
                "contact_info": request.contact_info,
                "created_at": request.created_at.isoformat(),
                "expiration_time": request.expiration_time.isoformat() if request.expiration_time else None,
                "message": self.format_request_message(request),
            }

            # Send webhook
            headers = {
                "Content-Type": "application/json",
            }

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers=headers,
                timeout=10,
            )

            response.raise_for_status()

            # Get message ID from response if available
            message_id = response.json().get("message_id") if response.content else None
            if not message_id:
                message_id = f"api_{request.reservation_id}_{datetime.utcnow().timestamp()}"

            return {
                "success": True,
                "message_id": message_id,
                "channel": "rest_api",
                "timestamp": datetime.utcnow().isoformat(),
                "response": response.json() if response.content else None,
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "channel": "rest_api",
                "timestamp": datetime.utcnow().isoformat(),
            }


class MockChannelHandler(CommunicationChannelHandler):
    """Mock handler for testing (logs to console/file instead of sending)."""

    def __init__(self, log_file: Optional[str] = None):
        """Initialize mock handler."""
        self.log_file = log_file
        self.sent_messages = []

    def send_request(
        self,
        request: ReservationRequest,
        admin_contact: str,
    ) -> Dict[str, Any]:
        """
        Mock send - log the request instead.

        Args:
            request: The reservation request
            admin_contact: Admin's contact (ignored in mock)

        Returns:
            Dictionary with success status and message_id
        """
        message = self.format_request_message(request)
        message_id = f"mock_{request.reservation_id}_{datetime.utcnow().timestamp()}"

        # Store in memory
        self.sent_messages.append({
            "message_id": message_id,
            "reservation": request.to_dict(),
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Log to file if specified
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Message ID: {message_id}\n")
                f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n")
                f.write(message)
                f.write(f"\n{'='*80}\n")

        # Log to console
        print(f"\n{'='*80}")
        print(f"📧 MOCK EMAIL/MESSAGE SENT")
        print(f"{'='*80}")
        print(message)
        print(f"{'='*80}\n")

        return {
            "success": True,
            "message_id": message_id,
            "channel": "mock",
            "timestamp": datetime.utcnow().isoformat(),
        }


def get_channel_handler(
    channel: CommunicationChannel,
    **kwargs,
) -> CommunicationChannelHandler:
    """
    Factory function to get the appropriate channel handler.

    Args:
        channel: The communication channel type
        **kwargs: Additional arguments for the handler

    Returns:
        The appropriate handler instance
    """
    if channel == CommunicationChannel.EMAIL:
        return EmailChannelHandler(**kwargs)
    elif channel == CommunicationChannel.REST_API:
        return RestAPIChannelHandler(**kwargs)
    elif channel == CommunicationChannel.WEBHOOK:
        return RestAPIChannelHandler(**kwargs)  # Webhooks use REST API handler
    else:
        # Default to mock for testing
        return MockChannelHandler(**kwargs)
