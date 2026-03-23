"""Dynamic data management using SQLAlchemy for real-time parking data."""

import os
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from src.data.schemas import ParkingSpace, Availability, PricingInfo, WorkingHours
from src.config.settings import get_settings

Base = declarative_base()


class ParkingSpaceDB(Base):
    """SQLAlchemy model for parking spaces."""
    __tablename__ = "parking_spaces"

    space_id = Column(String, primary_key=True)
    location = Column(String, nullable=False)
    space_type = Column(String, nullable=False)
    hourly_rate = Column(Float, nullable=False)
    daily_max = Column(Float)
    is_covered = Column(Boolean, default=False)
    has_ev_charging = Column(Boolean, default=False)
    is_accessible = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)


class AvailabilityDB(Base):
    """SQLAlchemy model for real-time availability."""
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_type = Column(String, nullable=False)
    available_spaces = Column(Integer, nullable=False)
    total_spaces = Column(Integer, nullable=False)
    last_updated = Column(DateTime, default=datetime.now)


class ReservationDB(Base):
    """SQLAlchemy model for reservations."""
    __tablename__ = "reservations"

    reservation_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    car_number = Column(String, nullable=False)
    space_type = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    email = Column(String)
    phone = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now)


class DynamicDataManager:
    """Manager for dynamic parking data operations."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the database manager."""
        settings = get_settings()
        self.database_url = database_url or settings.database_url

        # Ensure data directory exists
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def initialize_sample_data(self):
        """Initialize the database with sample data."""
        with self.get_session() as session:
            # Check if data already exists
            if session.query(ParkingSpaceDB).first():
                return

            # Sample parking spaces
            spaces = [
                ParkingSpaceDB(
                    space_id=f"STD-{i:03d}",
                    location="Level 1",
                    space_type="standard",
                    hourly_rate=3.00,
                    daily_max=25.00,
                    is_covered=False,
                ) for i in range(1, 51)
            ] + [
                ParkingSpaceDB(
                    space_id=f"COMP-{i:03d}",
                    location="Level 2",
                    space_type="compact",
                    hourly_rate=2.50,
                    daily_max=20.00,
                    is_covered=False,
                ) for i in range(1, 21)
            ] + [
                ParkingSpaceDB(
                    space_id=f"EV-{i:03d}",
                    location="Level 1",
                    space_type="ev_charging",
                    hourly_rate=4.00,
                    daily_max=35.00,
                    is_covered=False,
                    has_ev_charging=True,
                ) for i in range(1, 6)
            ] + [
                ParkingSpaceDB(
                    space_id=f"ACC-{i:03d}",
                    location="Level 1",
                    space_type="accessible",
                    hourly_rate=2.50,
                    daily_max=20.00,
                    is_covered=False,
                    is_accessible=True,
                ) for i in range(1, 11)
            ] + [
                ParkingSpaceDB(
                    space_id=f"COV-{i:03d}",
                    location="Rooftop",
                    space_type="covered",
                    hourly_rate=4.50,
                    daily_max=40.00,
                    is_covered=True,
                ) for i in range(1, 11)
            ] + [
                ParkingSpaceDB(
                    space_id=f"MC-{i:03d}",
                    location="Level 2",
                    space_type="motorcycle",
                    hourly_rate=1.50,
                    daily_max=12.00,
                    is_covered=False,
                ) for i in range(1, 6)
            ]

            session.add_all(spaces)

            # Sample availability
            availability_data = [
                AvailabilityDB(
                    space_type="standard",
                    available_spaces=42,
                    total_spaces=50,
                ),
                AvailabilityDB(
                    space_type="compact",
                    available_spaces=15,
                    total_spaces=20,
                ),
                AvailabilityDB(
                    space_type="ev_charging",
                    available_spaces=2,
                    total_spaces=5,
                ),
                AvailabilityDB(
                    space_type="accessible",
                    available_spaces=8,
                    total_spaces=10,
                ),
                AvailabilityDB(
                    space_type="covered",
                    available_spaces=7,
                    total_spaces=10,
                ),
                AvailabilityDB(
                    space_type="motorcycle",
                    available_spaces=4,
                    total_spaces=5,
                ),
            ]
            session.add_all(availability_data)

    def get_parking_spaces(
        self,
        space_type: Optional[str] = None,
        is_covered: Optional[bool] = None,
    ) -> List[ParkingSpace]:
        """Get parking spaces with optional filters."""
        with self.get_session() as session:
            query = session.query(ParkingSpaceDB).filter(ParkingSpaceDB.is_active == True)

            if space_type:
                query = query.filter(ParkingSpaceDB.space_type == space_type)
            if is_covered is not None:
                query = query.filter(ParkingSpaceDB.is_covered == is_covered)

            spaces_db = query.all()
            return [
                ParkingSpace(
                    space_id=s.space_id,
                    location=s.location,
                    space_type=s.space_type,
                    hourly_rate=s.hourly_rate,
                    daily_max=s.daily_max,
                    is_covered=s.is_covered,
                    has_ev_charging=s.has_ev_charging,
                    is_accessible=s.is_accessible,
                )
                for s in spaces_db
            ]

    def get_availability(self, space_type: str) -> Optional[Availability]:
        """Get current availability for a space type."""
        with self.get_session() as session:
            avail_db = session.query(AvailabilityDB).filter(
                AvailabilityDB.space_type == space_type
            ).first()

            if avail_db:
                return Availability(
                    space_type=avail_db.space_type,
                    available_spaces=avail_db.available_spaces,
                    total_spaces=avail_db.total_spaces,
                    last_updated=avail_db.last_updated,
                )
            return None

    def get_all_availabilities(self) -> List[Availability]:
        """Get availability for all space types."""
        with self.get_session() as session:
            avail_db = session.query(AvailabilityDB).all()
            return [
                Availability(
                    space_type=a.space_type,
                    available_spaces=a.available_spaces,
                    total_spaces=a.total_spaces,
                    last_updated=a.last_updated,
                )
                for a in avail_db
            ]

    def update_availability(
        self,
        space_type: str,
        available_spaces: int,
    ) -> bool:
        """Update availability for a space type."""
        with self.get_session() as session:
            avail = session.query(AvailabilityDB).filter(
                AvailabilityDB.space_type == space_type
            ).first()

            if avail:
                avail.available_spaces = available_spaces
                avail.last_updated = datetime.now()
                return True
            return False

    def get_pricing(self, space_type: str) -> Optional[PricingInfo]:
        """Get pricing information for a space type."""
        with self.get_session() as session:
            space = session.query(ParkingSpaceDB).filter(
                ParkingSpaceDB.space_type == space_type,
                ParkingSpaceDB.is_active == True,
            ).first()

            if space:
                return PricingInfo(
                    space_type=space.space_type,
                    hourly_rate=space.hourly_rate,
                    daily_rate=space.daily_max,
                )
            return None

    def get_all_pricing(self) -> List[PricingInfo]:
        """Get pricing for all space types."""
        with self.get_session() as session:
            spaces = session.query(ParkingSpaceDB).filter(
                ParkingSpaceDB.is_active == True
            ).distinct(ParkingSpaceDB.space_type).all()

            return [
                PricingInfo(
                    space_type=s.space_type,
                    hourly_rate=s.hourly_rate,
                    daily_rate=s.daily_max,
                )
                for s in spaces
            ]

    def create_reservation(
        self,
        name: str,
        surname: str,
        car_number: str,
        space_type: str,
        start_time: datetime,
        end_time: datetime,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> str:
        """Create a new reservation."""
        import uuid
        reservation_id = f"RES-{uuid.uuid4().hex[:8].upper()}"

        with self.get_session() as session:
            reservation = ReservationDB(
                reservation_id=reservation_id,
                name=name,
                surname=surname,
                car_number=car_number,
                space_type=space_type,
                start_time=start_time,
                end_time=end_time,
                email=email,
                phone=phone,
                status="pending",
            )
            session.add(reservation)

        return reservation_id

    def get_reservation(self, reservation_id: str) -> Optional[dict]:
        """Get reservation by ID."""
        with self.get_session() as session:
            res = session.query(ReservationDB).filter(
                ReservationDB.reservation_id == reservation_id
            ).first()

            if res:
                return {
                    "reservation_id": res.reservation_id,
                    "name": res.name,
                    "surname": res.surname,
                    "car_number": res.car_number,
                    "space_type": res.space_type,
                    "start_time": res.start_time,
                    "end_time": res.end_time,
                    "email": res.email,
                    "phone": res.phone,
                    "status": res.status,
                }
            return None


# Global database manager instance
_db_manager: Optional[DynamicDataManager] = None


def get_db_manager() -> DynamicDataManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DynamicDataManager()
        _db_manager.create_tables()
        _db_manager.initialize_sample_data()
    return _db_manager
