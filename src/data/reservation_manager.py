"""Reservation state manager for handling pending approvals."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session

from src.config.settings import get_settings
from src.data.reservation_state import (
    ReservationRequest,
    ReservationStatus,
    CommunicationChannel,
    ReservationRequestDB,
)


class ReservationManager:
    """Manages reservation requests and their approval states."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the reservation manager."""
        settings = get_settings()
        self.database_url = database_url or settings.database_url

        # Create engine and session
        self.engine = create_engine(self.database_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Create tables if they don't exist
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        from src.data.reservation_state import Base
        Base.metadata.create_all(self.engine)

    def create_reservation_request(
        self,
        user_name: str,
        user_surname: str,
        car_number: str,
        start_time: datetime,
        end_time: datetime,
        space_type: str,
        contact_info: str,
        communication_channel: CommunicationChannel = CommunicationChannel.EMAIL,
        expiration_hours: int = 24,
    ) -> ReservationRequest:
        """
        Create a new reservation request.

        Args:
            user_name: User's first name
            user_surname: User's last name
            car_number: License plate number
            start_time: Reservation start time
            end_time: Reservation end time
            space_type: Type of parking space
            contact_info: User's contact information
            communication_channel: How to contact the admin
            expiration_hours: Hours until the request expires

        Returns:
            The created ReservationRequest
        """
        reservation_id = str(uuid.uuid4())
        expiration_time = datetime.utcnow() + timedelta(hours=expiration_hours)

        request = ReservationRequest(
            reservation_id=reservation_id,
            user_name=user_name,
            user_surname=user_surname,
            car_number=car_number,
            start_time=start_time,
            end_time=end_time,
            space_type=space_type,
            contact_info=contact_info,
            communication_channel=communication_channel,
            expiration_time=expiration_time,
        )

        # Save to database
        db_request = ReservationRequestDB.from_reservation_request(request)
        self.session.add(db_request)
        self.session.commit()

        return request

    def get_reservation(self, reservation_id: str) -> Optional[ReservationRequest]:
        """
        Get a reservation by ID.

        Args:
            reservation_id: The reservation ID

        Returns:
            The ReservationRequest or None if not found
        """
        db_request = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.reservation_id == reservation_id
        ).first()

        if db_request:
            return db_request.to_reservation_request()
        return None

    def get_pending_reservations(self) -> List[ReservationRequest]:
        """
        Get all pending reservations.

        Returns:
            List of pending ReservationRequests
        """
        db_requests = self.session.query(ReservationRequestDB).filter(
            and_(
                ReservationRequestDB.status == "pending",
                or_(
                    ReservationRequestDB.expiration_time.is_(None),
                    ReservationRequestDB.expiration_time > datetime.utcnow()
                )
            )
        ).all()

        return [r.to_reservation_request() for r in db_requests]

    def update_reservation_status(
        self,
        reservation_id: str,
        status: ReservationStatus,
        admin_note: Optional[str] = None,
    ) -> Optional[ReservationRequest]:
        """
        Update reservation status.

        Args:
            reservation_id: The reservation ID
            status: New status
            admin_note: Optional note from admin

        Returns:
            Updated ReservationRequest or None if not found
        """
        db_request = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.reservation_id == reservation_id
        ).first()

        if not db_request:
            return None

        db_request.status = status.value
        db_request.updated_at = datetime.utcnow()
        if admin_note:
            db_request.admin_note = admin_note

        self.session.commit()
        return db_request.to_reservation_request()

    def approve_reservation(
        self,
        reservation_id: str,
        admin_note: Optional[str] = None,
    ) -> Optional[ReservationRequest]:
        """
        Approve a reservation.

        Args:
            reservation_id: The reservation ID
            admin_note: Optional note from admin

        Returns:
            Updated ReservationRequest or None if not found
        """
        return self.update_reservation_status(
            reservation_id,
            ReservationStatus.APPROVED,
            admin_note,
        )

    def reject_reservation(
        self,
        reservation_id: str,
        admin_note: Optional[str] = None,
    ) -> Optional[ReservationRequest]:
        """
        Reject a reservation.

        Args:
            reservation_id: The reservation ID
            admin_note: Optional note from admin

        Returns:
            Updated ReservationRequest or None if not found
        """
        return self.update_reservation_status(
            reservation_id,
            ReservationStatus.REJECTED,
            admin_note,
        )

    def cancel_reservation(self, reservation_id: str) -> Optional[ReservationRequest]:
        """
        Cancel a reservation (user action).

        Args:
            reservation_id: The reservation ID

        Returns:
            Updated ReservationRequest or None if not found
        """
        return self.update_reservation_status(
            reservation_id,
            ReservationStatus.CANCELLED,
        )

    def set_message_id(
        self,
        reservation_id: str,
        message_id: str,
    ) -> Optional[ReservationRequest]:
        """
        Set the message ID for a reservation (e.g., email ID, webhook ID).

        Args:
            reservation_id: The reservation ID
            message_id: The message ID

        Returns:
            Updated ReservationRequest or None if not found
        """
        db_request = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.reservation_id == reservation_id
        ).first()

        if not db_request:
            return None

        db_request.message_id = message_id
        db_request.updated_at = datetime.utcnow()
        self.session.commit()

        return db_request.to_reservation_request()

    def get_reservations_by_user(
        self,
        user_name: str,
        user_surname: Optional[str] = None,
    ) -> List[ReservationRequest]:
        """
        Get all reservations for a specific user.

        Args:
            user_name: User's first name
            user_surname: User's last name (optional)

        Returns:
            List of ReservationRequests
        """
        query = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.user_name == user_name
        )

        if user_surname:
            query = query.filter(ReservationRequestDB.user_surname == user_surname)

        db_requests = query.order_by(ReservationRequestDB.created_at.desc()).all()

        return [r.to_reservation_request() for r in db_requests]

    def cleanup_expired_reservations(self) -> int:
        """
        Mark expired reservations as expired.

        Returns:
            Number of reservations updated
        """
        db_requests = self.session.query(ReservationRequestDB).filter(
            and_(
                ReservationRequestDB.status == "pending",
                ReservationRequestDB.expiration_time < datetime.utcnow()
            )
        ).all()

        count = 0
        for db_request in db_requests:
            db_request.status = ReservationStatus.EXPIRED.value
            db_request.updated_at = datetime.utcnow()
            count += 1

        self.session.commit()
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get reservation statistics.

        Returns:
            Dictionary with statistics
        """
        total = self.session.query(ReservationRequestDB).count()
        pending = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.status == "pending"
        ).count()
        approved = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.status == "approved"
        ).count()
        rejected = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.status == "rejected"
        ).count()
        cancelled = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.status == "cancelled"
        ).count()
        expired = self.session.query(ReservationRequestDB).filter(
            ReservationRequestDB.status == "expired"
        ).count()

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "cancelled": cancelled,
            "expired": expired,
        }

    def close(self):
        """Close the database session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global instance
_reservation_manager: Optional[ReservationManager] = None


def get_reservation_manager() -> ReservationManager:
    """Get or create the global reservation manager instance."""
    global _reservation_manager
    if _reservation_manager is None:
        _reservation_manager = ReservationManager()
    return _reservation_manager
