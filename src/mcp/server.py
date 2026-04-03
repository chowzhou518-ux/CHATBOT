"""MCP (Model Context Protocol) Server for parking reservation system.

This server provides tools for:
- Writing approved reservations to persistent storage
- Reading reservation history
- Managing reservation files
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class ApprovedReservation(BaseModel):
    """Model for an approved reservation."""
    name: str = Field(..., description="Full name")
    car_number: str = Field(..., description="License plate number")
    reservation_period: str = Field(..., description="Start and end time")
    approval_time: str = Field(..., description="When the reservation was approved")
    reservation_id: str = Field(..., description="Unique reservation ID")
    space_type: str = Field(..., description="Type of parking space")
    contact_info: str = Field(..., description="User contact information")

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

    @validator('car_number')
    def car_number_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Car number cannot be empty')
        return v.strip().upper()

    def to_file_format(self) -> str:
        """Convert to file format: Name | Car Number | Reservation Period | Approval Time"""
        return f"{self.name} | {self.car_number} | {self.reservation_period} | {self.approval_time}"


class ReservationFileEntry(BaseModel):
    """Model for a reservation file entry."""
    entry: str = Field(..., description="Formatted entry string")
    timestamp: datetime = Field(default_factory=datetime.now)


class MCPToolRequest(BaseModel):
    """Model for MCP tool request."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class MCPToolResponse(BaseModel):
    """Model for MCP tool response."""
    success: bool
    tool_name: str
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Configuration
# ============================================================================

class MCPServerConfig:
    """MCP Server configuration."""

    def __init__(self):
        self.reservation_file = os.getenv(
            "RESERVATION_FILE",
            "./data/approved_reservations.txt"
        )
        self.backup_dir = os.getenv(
            "BACKUP_DIR",
            "./data/backups"
        )
        self.api_key = os.getenv("MCP_API_KEY", "")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
        self.enable_backup = os.getenv("ENABLE_BACKUP", "true").lower() == "true"
        self.require_auth = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

        # Create directories
        self._setup_directories()

    def _setup_directories(self):
        """Create necessary directories."""
        Path(self.reservation_file).parent.mkdir(parents=True, exist_ok=True)
        if self.enable_backup:
            Path(self.backup_dir).mkdir(parents=True, exist_ok=True)


# ============================================================================
# File Storage Manager
# ============================================================================

class ReservationStorageManager:
    """Manages reservation file storage."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.lock_file = os.path.join(
            Path(config.reservation_file).parent,
            ".reservations.lock"
        )

    def write_reservation(self, reservation: ApprovedReservation) -> bool:
        """
        Write an approved reservation to the file.

        Args:
            reservation: The approved reservation to write

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate file size
            if os.path.exists(self.config.reservation_file):
                file_size = os.path.getsize(self.config.reservation_file)
                if file_size > self.config.max_file_size:
                    logger.error(f"File size exceeds maximum: {file_size}")
                    return False

            # Create backup if enabled
            if self.config.enable_backup and os.path.exists(self.config.reservation_file):
                self._create_backup()

            # Append to file
            with open(self.config.reservation_file, 'a', encoding='utf-8') as f:
                f.write(reservation.to_file_format() + '\n')

            logger.info(f"Written reservation {reservation.reservation_id} to file")
            return True

        except Exception as e:
            logger.error(f"Error writing reservation: {e}")
            return False

    def read_all_reservations(self) -> List[str]:
        """Read all reservations from file."""
        try:
            if not os.path.exists(self.config.reservation_file):
                return []

            with open(self.config.reservation_file, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]

        except Exception as e:
            logger.error(f"Error reading reservations: {e}")
            return []

    def search_reservations(self, query: str) -> List[str]:
        """Search reservations by name or car number."""
        all_reservations = self.read_all_reservations()
        query_lower = query.lower()

        return [
            r for r in all_reservations
            if query_lower in r.lower()
        ]

    def _create_backup(self):
        """Create a backup of the current reservation file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                self.config.backup_dir,
                f"reservations_backup_{timestamp}.txt"
            )

            import shutil
            shutil.copy2(self.config.reservation_file, backup_path)
            logger.info(f"Created backup: {backup_path}")

        except Exception as e:
            logger.error(f"Error creating backup: {e}")

    def get_file_stats(self) -> Dict[str, Any]:
        """Get file statistics."""
        try:
            if not os.path.exists(self.config.reservation_file):
                return {
                    "exists": False,
                    "total_reservations": 0,
                }

            stat = os.stat(self.config.reservation_file)
            reservations = self.read_all_reservations()

            return {
                "exists": True,
                "total_reservations": len(reservations),
                "file_size": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_path": self.config.reservation_file,
            }

        except Exception as e:
            logger.error(f"Error getting file stats: {e}")
            return {"error": str(e)}


# ============================================================================
# MCP Tools Implementation
# ============================================================================

class MCPTools:
    """Collection of MCP tools for reservation management."""

    def __init__(self, storage_manager: ReservationStorageManager):
        self.storage = storage_manager

    def write_approved_reservation(self, reservation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool: Write an approved reservation to file.

        Args:
            reservation_data: Dictionary with reservation details

        Returns:
            Success status and details
        """
        try:
            reservation = ApprovedReservation(**reservation_data)

            success = self.storage.write_reservation(reservation)

            if success:
                return {
                    "success": True,
                    "message": f"Reservation {reservation.reservation_id} written to file",
                    "entry": reservation.to_file_format(),
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to write reservation to file",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}",
            }

    def read_reservations(self, filter_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Tool: Read reservations from file.

        Args:
            filter_query: Optional search query

        Returns:
            List of reservations
        """
        try:
            if filter_query:
                reservations = self.storage.search_reservations(filter_query)
            else:
                reservations = self.storage.read_all_reservations()

            return {
                "success": True,
                "count": len(reservations),
                "reservations": reservations,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}",
            }

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Tool: Get storage statistics.

        Returns:
            File statistics
        """
        return self.storage.get_file_stats()

    def delete_all_reservations(self) -> Dict[str, Any]:
        """
        Tool: Delete all reservations (with backup).

        Returns:
            Success status
        """
        try:
            if os.path.exists(self.storage.config.reservation_file):
                self.storage._create_backup()
                os.remove(self.storage.config.reservation_file)
                return {
                    "success": True,
                    "message": "All reservations deleted (backup created)",
                }
            else:
                return {
                    "success": True,
                    "message": "No reservations to delete",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}",
            }


# ============================================================================
# FastAPI Server
# ============================================================================

app = FastAPI(
    title="Parking Reservation MCP Server",
    description="MCP server for managing approved parking reservations",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
config = MCPServerConfig()
storage_manager = ReservationStorageManager(config)
mcp_tools = MCPTools(storage_manager)


# ============================================================================
# Authentication Middleware
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Verify API key if authentication is required."""
    if config.require_auth:
        if not config.api_key:
            raise HTTPException(
                status_code=500,
                detail="Server configured to require authentication but no API key is set"
            )

        if x_api_key != config.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key"
            )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Parking Reservation MCP Server",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "tools": [
            "write_approved_reservation",
            "read_reservations",
            "get_storage_stats",
            "delete_all_reservations",
        ],
    }


@app.post("/mcp/tool/write_reservation")
async def mcp_write_reservation(
    reservation: ApprovedReservation,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None),
):
    """
    MCP Tool: Write an approved reservation to file.

    This endpoint is called when a reservation is approved by the administrator.
    """
    await verify_api_key(x_api_key)

    result = mcp_tools.write_approved_reservation(reservation.dict())

    if result["success"]:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": result["message"],
                "entry": result["entry"],
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": result.get("error")}
        )


@app.post("/mcp/tool/read_reservations")
async def mcp_read_reservations(
    filter_query: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """MCP Tool: Read reservations from file."""
    await verify_api_key(x_api_key)

    result = mcp_tools.read_reservations(filter_query)

    return JSONResponse(status_code=200, content=result)


@app.get("/mcp/tool/storage_stats")
async def mcp_storage_stats(
    x_api_key: Optional[str] = Header(None),
):
    """MCP Tool: Get storage statistics."""
    await verify_api_key(x_api_key)

    stats = mcp_tools.get_storage_stats()
    return JSONResponse(status_code=200, content=stats)


@app.delete("/mcp/tool/all_reservations")
async def mcp_delete_all(
    x_api_key: Optional[str] = Header(None),
):
    """MCP Tool: Delete all reservations."""
    await verify_api_key(x_api_key)

    result = mcp_tools.delete_all_reservations()
    return JSONResponse(status_code=200, content=result)


@app.post("/mcp/execute")
async def mcp_execute_tool(
    request: MCPToolRequest,
    x_api_key: Optional[str] = Header(None),
):
    """
    Generic MCP tool execution endpoint.

    Executes a tool by name with parameters.
    """
    await verify_api_key(x_api_key)

    tool_map = {
        "write_approved_reservation": mcp_tools.write_approved_reservation,
        "read_reservations": mcp_tools.read_reservations,
        "get_storage_stats": mcp_tools.get_storage_stats,
        "delete_all_reservations": mcp_tools.delete_all_reservations,
    }

    tool = tool_map.get(request.tool_name)

    if not tool:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Tool '{request.tool_name}' not found"
            }
        )

    try:
        result = tool(**request.parameters)
        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
            }
        )


# ============================================================================
# Integration Function
# ============================================================================

def save_approved_reservation(
    name: str,
    surname: str,
    car_number: str,
    start_time: datetime,
    end_time: datetime,
    reservation_id: str,
    space_type: str,
    contact_info: str,
    mcp_server_url: str = "http://localhost:8001",
) -> bool:
    """
    Convenience function to save an approved reservation via MCP server.

    Args:
        name: User's first name
        surname: User's last name
        car_number: License plate
        start_time: Reservation start time
        end_time: Reservation end time
        reservation_id: Unique ID
        space_type: Type of parking space
        contact_info: User contact
        mcp_server_url: MCP server URL

    Returns:
        True if successful
    """
    try:
        import requests

        period = f"{start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}"
        approval_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        reservation = ApprovedReservation(
            name=f"{name} {surname}",
            car_number=car_number,
            reservation_period=period,
            approval_time=approval_time,
            reservation_id=reservation_id,
            space_type=space_type,
            contact_info=contact_info,
        )

        response = requests.post(
            f"{mcp_server_url}/mcp/tool/write_reservation",
            json=reservation.dict(),
            timeout=5,
        )

        return response.status_code == 200

    except Exception as e:
        logger.error(f"Error saving reservation via MCP: {e}")
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚗 PARKING RESERVATION MCP SERVER")
    print("="*80)
    print(f"📁 Reservation File: {config.reservation_file}")
    print(f"🔒 Authentication: {'Enabled' if config.require_auth else 'Disabled'}")
    print(f"💾 Backup: {'Enabled' if config.enable_backup else 'Disabled'}")
    print(f"🚀 Server starting on http://0.0.0.0:8001")
    print("="*80 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
