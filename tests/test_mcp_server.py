"""Tests for MCP server."""

import pytest
import os
import tempfile
from datetime import datetime
from pathlib import Path

from src.mcp.server import (
    ApprovedReservation,
    MCPServerConfig,
    ReservationStorageManager,
    MCPTools,
    save_approved_reservation,
)


class TestApprovedReservation:
    """Test ApprovedReservation model."""

    def test_create_reservation(self):
        """Test creating a reservation."""
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="ABC-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        assert reservation.name == "John Doe"
        assert reservation.car_number == "ABC-123"

    def test_to_file_format(self):
        """Test converting to file format."""
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="abc-123",  # Test uppercase
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        file_format = reservation.to_file_format()

        assert "John Doe" in file_format
        assert "ABC-123" in file_format  # Should be uppercase
        assert "2026-04-10 10:00 - 2026-04-10 12:00" in file_format
        assert "2026-04-10 09:00:00" in file_format

    def test_name_validation(self):
        """Test name validation."""
        with pytest.raises(ValueError):
            ApprovedReservation(
                name="",
                car_number="ABC-123",
                reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
                approval_time="2026-04-10 09:00:00",
                reservation_id="test-123",
                space_type="standard",
                contact_info="john@example.com",
            )

    def test_car_number_validation(self):
        """Test car number validation."""
        with pytest.raises(ValueError):
            ApprovedReservation(
                name="John Doe",
                car_number="",
                reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
                approval_time="2026-04-10 09:00:00",
                reservation_id="test-123",
                space_type="standard",
                contact_info="john@example.com",
            )

    def test_car_number_uppercase(self):
        """Test car number is converted to uppercase."""
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="abc-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        assert reservation.car_number == "ABC-123"


class TestMCPServerConfig:
    """Test MCPServerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = MCPServerConfig()

        assert config.reservation_file == "./data/approved_reservations.txt"
        assert config.backup_dir == "./data/backups"
        assert config.max_file_size == 10485760  # 10MB
        assert config.enable_backup is True
        assert config.require_auth is True

    def test_setup_directories(self, tmp_path):
        """Test directory setup."""
        config = MCPServerConfig()
        config.reservation_file = str(tmp_path / "reservations.txt")
        config.backup_dir = str(tmp_path / "backups")
        config._setup_directories()

        # Check that backup directory was created
        assert os.path.exists(config.backup_dir)


class TestReservationStorageManager:
    """Test ReservationStorageManager."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config for testing."""
        config = MCPServerConfig()
        config.reservation_file = str(tmp_path / "reservations.txt")
        config.backup_dir = str(tmp_path / "backups")
        config.enable_backup = True
        return config

    @pytest.fixture
    def storage_manager(self, temp_config):
        """Create a storage manager for testing."""
        return ReservationStorageManager(temp_config)

    def test_write_reservation(self, storage_manager):
        """Test writing a reservation to file."""
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="ABC-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        result = storage_manager.write_reservation(reservation)

        assert result is True
        assert os.path.exists(storage_manager.config.reservation_file)

    def test_write_multiple_reservations(self, storage_manager):
        """Test writing multiple reservations."""
        reservations = [
            ApprovedReservation(
                name=f"User {i}",
                car_number=f"CAR-{i}",
                reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
                approval_time="2026-04-10 09:00:00",
                reservation_id=f"test-{i}",
                space_type="standard",
                contact_info=f"user{i}@example.com",
            )
            for i in range(3)
        ]

        for res in reservations:
            storage_manager.write_reservation(res)

        all_reservations = storage_manager.read_all_reservations()
        assert len(all_reservations) == 3

    def test_read_reservations(self, storage_manager):
        """Test reading reservations from file."""
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="ABC-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        storage_manager.write_reservation(reservation)
        reservations = storage_manager.read_all_reservations()

        assert len(reservations) == 1
        assert "John Doe" in reservations[0]
        assert "ABC-123" in reservations[0]

    def test_search_reservations(self, storage_manager):
        """Test searching reservations."""
        reservations = [
            ApprovedReservation(
                name="John Doe",
                car_number="ABC-123",
                reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
                approval_time="2026-04-10 09:00:00",
                reservation_id="test-1",
                space_type="standard",
                contact_info="john@example.com",
            ),
            ApprovedReservation(
                name="Jane Smith",
                car_number="XYZ-789",
                reservation_period="2026-04-10 14:00 - 2026-04-10 16:00",
                approval_time="2026-04-10 13:00:00",
                reservation_id="test-2",
                space_type="compact",
                contact_info="jane@example.com",
            ),
        ]

        for res in reservations:
            storage_manager.write_reservation(res)

        # Search by name
        results = storage_manager.search_reservations("John")
        assert len(results) == 1
        assert "John Doe" in results[0]

        # Search by car number
        results = storage_manager.search_reservations("XYZ")
        assert len(results) == 1
        assert "Jane Smith" in results[0]

    def test_get_file_stats(self, storage_manager):
        """Test getting file statistics."""
        stats = storage_manager.get_file_stats()

        # File doesn't exist yet
        assert stats["exists"] is False
        assert stats["total_reservations"] == 0

        # Add a reservation
        reservation = ApprovedReservation(
            name="John Doe",
            car_number="ABC-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        storage_manager.write_reservation(reservation)
        stats = storage_manager.get_file_stats()

        assert stats["exists"] is True
        assert stats["total_reservations"] == 1
        assert "file_size" in stats

    def test_create_backup(self, storage_manager):
        """Test backup creation."""
        # Ensure backup directory exists
        os.makedirs(storage_manager.config.backup_dir, exist_ok=True)

        reservation = ApprovedReservation(
            name="John Doe",
            car_number="ABC-123",
            reservation_period="2026-04-10 10:00 - 2026-04-10 12:00",
            approval_time="2026-04-10 09:00:00",
            reservation_id="test-123",
            space_type="standard",
            contact_info="john@example.com",
        )

        storage_manager.write_reservation(reservation)
        storage_manager._create_backup()

        # Check backup exists
        backup_files = list(Path(storage_manager.config.backup_dir).glob("*.txt"))
        assert len(backup_files) > 0


class TestMCPTools:
    """Test MCPTools."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config for testing."""
        config = MCPServerConfig()
        config.reservation_file = str(tmp_path / "reservations.txt")
        config.backup_dir = str(tmp_path / "backups")
        return config

    @pytest.fixture
    def mcp_tools(self, temp_config):
        """Create MCP tools for testing."""
        storage_manager = ReservationStorageManager(temp_config)
        return MCPTools(storage_manager)

    def test_write_approved_reservation(self, mcp_tools):
        """Test write_approved_reservation tool."""
        reservation_data = {
            "name": "John Doe",
            "car_number": "ABC-123",
            "reservation_period": "2026-04-10 10:00 - 2026-04-10 12:00",
            "approval_time": "2026-04-10 09:00:00",
            "reservation_id": "test-123",
            "space_type": "standard",
            "contact_info": "john@example.com",
        }

        result = mcp_tools.write_approved_reservation(reservation_data)

        assert result["success"] is True
        assert "entry" in result

    def test_read_reservations(self, mcp_tools):
        """Test read_reservations tool."""
        # First write a reservation
        reservation_data = {
            "name": "John Doe",
            "car_number": "ABC-123",
            "reservation_period": "2026-04-10 10:00 - 2026-04-10 12:00",
            "approval_time": "2026-04-10 09:00:00",
            "reservation_id": "test-123",
            "space_type": "standard",
            "contact_info": "john@example.com",
        }

        mcp_tools.write_approved_reservation(reservation_data)

        # Read reservations
        result = mcp_tools.read_reservations()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["reservations"]) == 1

    def test_read_reservations_with_filter(self, mcp_tools):
        """Test read_reservations with filter."""
        # Write multiple reservations
        reservations = [
            {
                "name": "John Doe",
                "car_number": "ABC-123",
                "reservation_period": "2026-04-10 10:00 - 2026-04-10 12:00",
                "approval_time": "2026-04-10 09:00:00",
                "reservation_id": "test-1",
                "space_type": "standard",
                "contact_info": "john@example.com",
            },
            {
                "name": "Jane Smith",
                "car_number": "XYZ-789",
                "reservation_period": "2026-04-10 14:00 - 2026-04-10 16:00",
                "approval_time": "2026-04-10 13:00:00",
                "reservation_id": "test-2",
                "space_type": "compact",
                "contact_info": "jane@example.com",
            },
        ]

        for res in reservations:
            mcp_tools.write_approved_reservation(res)

        # Filter by name
        result = mcp_tools.read_reservations(filter_query="John")

        assert result["success"] is True
        assert result["count"] == 1
        assert "John Doe" in result["reservations"][0]

    def test_get_storage_stats(self, mcp_tools):
        """Test get_storage_stats tool."""
        stats = mcp_tools.get_storage_stats()

        assert "total_reservations" in stats
        assert stats["total_reservations"] == 0

    def test_delete_all_reservations(self, mcp_tools):
        """Test delete_all_reservations tool."""
        # Write a reservation first
        reservation_data = {
            "name": "John Doe",
            "car_number": "ABC-123",
            "reservation_period": "2026-04-10 10:00 - 2026-04-10 12:00",
            "approval_time": "2026-04-10 09:00:00",
            "reservation_id": "test-123",
            "space_type": "standard",
            "contact_info": "john@example.com",
        }

        mcp_tools.write_approved_reservation(reservation_data)

        # Delete all
        result = mcp_tools.delete_all_reservations()

        assert result["success"] is True

        # Verify deletion
        stats = mcp_tools.get_storage_stats()
        assert stats["total_reservations"] == 0
