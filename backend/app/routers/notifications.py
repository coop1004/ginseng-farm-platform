from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_household_id

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationOut])
def list_my_notifications(household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    """로그인한 농가로 온 처방 알림만 조회 (관리자용 /api/admin/notifications 와 별개)."""
    notifications = (
        db.query(models.Notification)
        .join(models.Farm, models.Notification.farm_id == models.Farm.id)
        .filter(models.Farm.household_id == household_id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )
    results = []
    for n in notifications:
        out = schemas.NotificationOut.model_validate(n)
        out.farm_name = n.farm.farm_name if n.farm else None
        results.append(out)
    return results
