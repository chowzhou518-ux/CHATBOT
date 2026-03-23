"""Data models and schemas for the parking chatbot."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ParkingType(str, Enum):
    """Types of parking spaces."""
    STANDARD = "standard"
    COMPACT = "compact"
    EV_CHARGING = "ev_charging"
    ACCESSIBLE = "accessible"
    COVERED = "covered"
    MOTORCYCLE = "motorcycle"


class ParkingSpace(BaseModel):
    """Model for a parking space."""
    space_id: str = Field(..., description="Unique identifier for the parking space")
    location: str = Field(..., description="Location/area within the parking facility")
    space_type: ParkingType = Field(default=ParkingType.STANDARD, description="Type of parking space")
    hourly_rate: float = Field(..., ge=0, description="Hourly parking rate")
    daily_max: Optional[float] = Field(default=None, ge=0, description="Maximum daily rate")
    is_covered: bool = Field(default=False, description="Whether the space is covered")
    has_ev_charging: bool = Field(default=False, description="Whether the space has EV charging")
    is_accessible: bool = Field(default=False, description="Whether the space is accessible")

    @field_validator("hourly_rate")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        """Validate rate is reasonable."""
        if v > 100:
            raise ValueError("Hourly rate seems too high")
        return round(v, 2)


class Reservation(BaseModel):
    """Model for a parking reservation."""
    reservation_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100, description="Customer first name")
    surname: str = Field(..., min_length=1, max_length=100, description="Customer last name")
    car_number: str = Field(..., min_length=1, max_length=20, description="License plate number")
    space_type: ParkingType = Field(default=ParkingType.STANDARD, description="Requested space type")
    start_time: datetime = Field(..., description="Reservation start time")
    end_time: datetime = Field(..., description="Reservation end time")
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone")
    status: str = Field(default="pending", description="Reservation status")
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: datetime, info) -> datetime:
        """Validate end time is after start time."""
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    @property
    def duration_hours(self) -> float:
        """Calculate reservation duration in hours."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600


class Availability(BaseModel):
    """Model for parking space availability."""
    space_type: ParkingType = Field(..., description="Type of parking space")
    available_spaces: int = Field(..., ge=0, description="Number of available spaces")
    total_spaces: int = Field(..., ge=0, description="Total number of spaces")
    last_updated: datetime = Field(default_factory=datetime.now)

    @property
    def utilization_percentage(self) -> float:
        """Calculate current utilization percentage."""
        if self.total_spaces == 0:
            return 0.0
        return ((self.total_spaces - self.available_spaces) / self.total_spaces) * 100


class PricingInfo(BaseModel):
    """Model for pricing information."""
    space_type: ParkingType = Field(..., description="Type of parking space")
    hourly_rate: float = Field(..., ge=0, description="Hourly rate")
    daily_rate: Optional[float] = Field(default=None, description="Daily rate")
    weekly_rate: Optional[float] = Field(default=None, description="Weekly rate")

    @field_validator("hourly_rate", "daily_rate", "weekly_rate")
    @classmethod
    def round_rate(cls, v: Optional[float]) -> Optional[float]:
        """Round rates to 2 decimal places."""
        return round(v, 2) if v is not None else None


class WorkingHours(BaseModel):
    """Model for facility working hours."""
    day_of_week: str = Field(..., description="Day of the week")
    open_time: str = Field(..., description="Opening time (HH:MM format)")
    close_time: str = Field(..., description="Closing time (HH:MM format)")
    is_24_hours: bool = Field(default=False, description="Whether open 24 hours this day")


class LocationInfo(BaseModel):
    """Model for parking facility location information."""
    name: str = Field(..., description="Facility name")
    address: str = Field(..., description="Street address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State/Province")
    postal_code: str = Field(..., description="Postal/ZIP code")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90, description="GPS latitude")
    longitude: Optional[float] = Field(default=None, ge=-180, le=180, description="GPS longitude")
    total_spaces: int = Field(..., ge=0, description="Total parking spaces")
