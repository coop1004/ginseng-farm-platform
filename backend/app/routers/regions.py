from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("", response_model=List[schemas.AdministrativeRegionOut])
def list_regions(db: Session = Depends(get_db)):
    """전국 시/군/구 표준 목록 (공개, 인증 불필요) - 농장 등록 화면의 지역 선택
    드롭다운이 사용한다."""
    return (
        db.query(models.AdministrativeRegion)
        .order_by(models.AdministrativeRegion.sort_order)
        .all()
    )
