"""Reservation state management for human-in-the-loop approval system."""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import json

from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base

from src.data.schemas import Base


class ReservationStatus(str, Enum):
    """Reservation status enum."""
    PENDING = "pending"              # Awaiting admin approval
    APPROVED = "approved"            # Approved by admin
    REJECTED = "rejected"            # Rejected by admin
    CANCELLED = "cancelled"          # Cancelled by user
    EXPIRED = "expired"              # Approval request expired


class CommunicationChannel(str, Enum):
    """Communication channel types."""
    EMAIL = "email"
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    SMS = "sms"


@dataclass
class ReservationRequest:
    """Represents a reservation request awaiting admin approval."""
    reservation_id: str
    user_name: str
    user_surname: str
    car_number: str
    start_time: datetime
    end_time: datetime
    space_type: str
    contact_info: str
    status: ReservationStatus = ReservationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    admin_note: Optional[str] = None
    communication_channel: CommunicationChannel = CommunicationChannel.EMAIL
    message_id: Optional[str] = None  # ID of the message sent to admin
    expiration_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reservation_id": self.reservation_id,
            "user_name": self.user_name,
            "user_surname": self.user_surname,
            "car_number": self.car_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "space_type": self.space_type,
            "contact_info": self.contact_info,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "admin_note": self.admin_note,
            "communication_channel": self.communication_channel.value,
            "message_id": self.message_id,
            "expiration_time": self.expiration_time.isoformat() if self.expiration_time else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReservationRequest":
        """Create from dictionary."""
        return cls(
            reservation_id=data["reservation_id"],
            user_name=data["user_name"],
            user_surname=data["user_surname"],
            car_number=data["car_number"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            space_type=data["space_type"],
            contact_info=data["contact_info"],
            status=ReservationStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            admin_note=data.get("admin_note"),
            communication_channel=CommunicationChannel(data.get("communication_channel", "email")),
            message_id=data.get("message_id"),
            expiration_time=datetime.fromisoformat(data["expiration_time"]) if data.get("expiration_time") else None,
        )

    def is_expired(self) -> bool:
        """Check if the reservation request has expired."""
        if self.expiration_time is None:
            return False
        return datetime.utcnow() > self.expiration_time

    def can_be_approved(self) -> bool:
        """Check if the reservation can still be approved."""
        return self.status == ReservationStatus.PENDING and not self.is_expired()


class ReservationRequestDB(Base):
    """SQLAlchemy model for reservation requests."""
    __tablename__ = "reservation_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(String(36), unique=True, nullable=False, index=True)
    user_name = Column(String(100), nullable=False)
    user_surname = Column(String(100), nullable=False)
    car_number = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    space_type = Column(String(50), nullable=False)
    contact_info = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_note = Column(Text, nullable=True)
    communication_channel = Column(String(20), nullable=False, default="email")
    message_id = Column(String(100), nullable=True)
    expiration_time = Column(DateTime, nullable=True)

    def to_reservation_request(self) -> ReservationRequest:
        """Convert to ReservationRequest dataclass."""
        return ReservationRequest(
            reservation_id=self.reservation_id,
            user_name=self.user_name,
            user_surname=self.user_surname,
            car_number=self.car_number,
            start_time=self.start_time,
            end_time=self.end_time,
            space_type=self.space_type,
            contact_info=self.contact_info,
            status=ReservationStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
            admin_note=self.admin_note,
            communication_channel=CommunicationChannel(self.communication_channel),
            message_id=self.message_id,
            expiration_time=self.expiration_time,
        )

    @classmethod
    def from_reservation_request(cls, request: ReservationRequest) -> "ReservationRequestDB":
        """Create from ReservationRequest dataclass."""
        return cls(
            reservation_id=request.reservation_id,
            user_name=request.user_name,
            user_surname=request.user_surname,
            car_number=request.car_number,
            start_time=request.start_time,
            end_time=request.end_time,
            space_type=request.space_type,
            contact_info=request.contact_info,
            status=request.status.value,
            created_at=request.created_at,
            updated_at=request.updated_at,
            admin_note=request.admin_note,
            communication_channel=request.communication_channel.value,
            message_id=request.message_id,
            expiration_time=request.expiration_time,
        )
