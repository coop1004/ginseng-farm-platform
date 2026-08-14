from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/crops", tags=["crops"])


@router.get("", response_model=List[schemas.CropOut])
def list_crops(db: Session = Depends(get_db)):
    """지원 작물 목록 (공개, 인증 불필요) — 모바일 앱의 작물 선택 UI, 관리자 대시보드
    CMS의 작물 드롭다운 양쪽에서 사용한다."""
    return (
        db.query(models.Crop)
        .filter(models.Crop.is_active.is_(True))
        .order_by(models.Crop.sort_order)
        .all()
    )


@router.get("/{crop_id}/growth-stages", response_model=List[schemas.GrowthStageOut])
def list_growth_stages(crop_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.GrowthStage)
        .filter(models.GrowthStage.crop_id == crop_id)
        .order_by(models.GrowthStage.sort_order)
        .all()
    )
