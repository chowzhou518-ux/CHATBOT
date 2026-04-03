"""REST API server for administrator notifications and responses."""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uvicorn

from src.chatbot.escalation import get_escalation_manager
from src.data.reservation_manager import get_reservation_manager
from src.data.reservation_state import ReservationStatus


# Pydantic models
class ReservationNotification(BaseModel):
    """Model for reservation notification payload."""
    reservation_id: str
    user_name: str
    user_surname: str
    car_number: str
    space_type: str
    start_time: datetime
    end_time: datetime
    contact_info: str
    created_at: datetime
    expiration_time: Optional[datetime] = None
    message: str


class AdminResponse(BaseModel):
    """Model for administrator response."""
    action: str = Field(..., description="Either 'approve' or 'reject'")
    reservation_id: str
    reason: Optional[str] = None
    note: Optional[str] = None


class StatusResponse(BaseModel):
    """Model for status check response."""
    success: bool
    reservation_id: str
    status: str
    can_be_approved: bool
    is_expired: bool
    created_at: datetime
    updated_at: datetime
    expiration_time: Optional[datetime] = None
    admin_note: Optional[str] = None


# Initialize FastAPI app
app = FastAPI(
    title="Parking Reservation API",
    description="API for administrator notifications and reservation management",
    version="2.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global components
escalation_manager = get_escalation_manager()
reservation_manager = get_reservation_manager()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Parking Reservation API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/webhook/reservation")
async def receive_reservation_notification(
    notification: ReservationNotification,
    background_tasks: BackgroundTasks,
):
    """
    Webhook endpoint to receive reservation notifications.

    This is where the system sends notifications when users submit reservations.
    In production, this would be called by the escalation system.
    """
    # Store the notification (in production, add to queue/database)
    print(f"\n📧 Reservation notification received:")
    print(f"  ID: {notification.reservation_id}")
    print(f"  User: {notification.user_name} {notification.user_surname}")
    print(f"  Car: {notification.car_number}")
    print(f"  Time: {notification.start_time} - {notification.end_time}")

    return {
        "success": True,
        "message": "Notification received",
        "reservation_id": notification.reservation_id,
    }


@app.post("/api/admin/respond")
async def handle_admin_response(response: AdminResponse):
    """
    Handle administrator's approval/rejection response.

    Args:
        response: Admin response with action, reservation_id, and optional reason

    Returns:
        Result of the action
    """
    try:
        if response.action.lower() == "approve":
            reservation = reservation_manager.approve_reservation(
                response.reservation_id,
                admin_note=response.note,
            )

            if not reservation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Reservation {response.reservation_id} not found",
                )

            return {
                "success": True,
                "action": "approved",
                "reservation_id": response.reservation_id,
                "message": f"Reservation {response.reservation_id} approved successfully",
                "reservation": reservation.to_dict(),
            }

        elif response.action.lower() == "reject":
            reservation = reservation_manager.reject_reservation(
                response.reservation_id,
                admin_note=response.reason or response.note,
            )

            if not reservation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Reservation {response.reservation_id} not found",
                )

            return {
                "success": True,
                "action": "rejected",
                "reservation_id": response.reservation_id,
                "message": f"Reservation {response.reservation_id} rejected",
                "reservation": reservation.to_dict(),
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {response.action}. Use 'approve' or 'reject'.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing response: {str(e)}",
        )


@app.get("/api/reservations/{reservation_id}")
async def get_reservation(reservation_id: str):
    """Get details of a specific reservation."""
    reservation = reservation_manager.get_reservation(reservation_id)

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"Reservation {reservation_id} not found",
        )

    return {
        "success": True,
        "reservation": reservation.to_dict(),
    }


@app.get("/api/reservations")
async def list_reservations(status: Optional[str] = None):
    """List reservations, optionally filtered by status."""
    if status == "pending":
        reservations = reservation_manager.get_pending_reservations()
    else:
        # For now, only support pending
        reservations = reservation_manager.get_pending_reservations()

    return {
        "success": True,
        "count": len(reservations),
        "reservations": [r.to_dict() for r in reservations],
    }


@app.get("/api/stats")
async def get_statistics():
    """Get reservation statistics."""
    stats = reservation_manager.get_statistics()

    return {
        "success": True,
        "statistics": stats,
    }


@app.post("/api/cleanup")
async def cleanup_expired():
    """Clean up expired reservations."""
    count = reservation_manager.cleanup_expired_reservations()

    return {
        "success": True,
        "expired_count": count,
        "message": f"Marked {count} reservation(s) as expired",
    }


if __name__ == "__main__":
    print("\n🚀 Starting Parking Reservation API Server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API docs available at: http://localhost:8000/docs")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
