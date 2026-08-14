from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_household_crop_ids

router = APIRouter(prefix="/api/crops", tags=["crops"])


@router.get("", response_model=List[schemas.CropOut])
def list_crops(db: Session = Depends(get_db)):
    """지원 작물 전체 목록 (공개, 인증 불필요) — 회원가입 시 작물 선택 화면, 관리자 대시보드
    CMS의 작물 드롭다운처럼 "농가가 아직 뭘 등록했는지"와 무관하게 전체가 필요한 곳에서 쓴다.
    농가 로그인 이후 화면(작물 전환, 농장 등록 등)은 대신 GET /api/crops/mine을 써야 한다."""
    return (
        db.query(models.Crop)
        .filter(models.Crop.is_active.is_(True))
        .order_by(models.Crop.sort_order)
        .all()
    )


@router.get("/mine", response_model=List[schemas.CropOut])
def list_my_crops(crop_ids: List[int] = Depends(get_household_crop_ids), db: Session = Depends(get_db)):
    """로그인한 농가가 등록한 작물만 반환. 모바일의 작물 전환 스위처, 농장 등록 화면의
    작물 드롭다운, 병해충 참고자료 화면의 기본 작물 목록이 전부 이걸 쓴다."""
    if not crop_ids:
        return []
    return (
        db.query(models.Crop)
        .filter(models.Crop.id.in_(crop_ids), models.Crop.is_active.is_(True))
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
