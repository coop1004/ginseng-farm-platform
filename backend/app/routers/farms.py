from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id, get_household_crop_ids
from app.seed import get_ginseng_crop_id

router = APIRouter(prefix="/api/farms", tags=["farms"])


def _to_out(f: models.Farm) -> dict:
    return {
        **{c.name: getattr(f, c.name) for c in f.__table__.columns},
        "household_name": f.household.name if f.household else None,
        "crop_name": f.crop.name_kr if f.crop else None,
        "growth_stage_name": f.growth_stage.name_kr if f.growth_stage else None,
    }


def _ensure_crop_registered(crop_id: int, household_crop_ids: List[int]) -> None:
    if crop_id not in household_crop_ids:
        raise HTTPException(status_code=403, detail="등록하지 않은 작물로는 농장을 만들 수 없습니다. 먼저 작물을 등록해주세요.")


@router.post("", response_model=schemas.FarmOut)
def create_farm(
    payload: schemas.FarmCreate,
    household_id: int = Depends(get_current_household_id),
    household_crop_ids: List[int] = Depends(get_household_crop_ids),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    if data.get("crop_id") is None:
        # 구버전 모바일 클라이언트(작물 선택 UI 도입 이전)는 crop_id를 안 보낸다 -> 인삼으로 기본값 처리
        data["crop_id"] = get_ginseng_crop_id(db)
    _ensure_crop_registered(data["crop_id"], household_crop_ids)
    farm = models.Farm(household_id=household_id, **data)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return _to_out(farm)


@router.get("", response_model=List[schemas.FarmOut])
def list_farms(household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    farms = (
        db.query(models.Farm)
        .filter(models.Farm.household_id == household_id)
        .order_by(models.Farm.created_at.desc())
        .all()
    )
    return [_to_out(f) for f in farms]


@router.get("/{farm_id}", response_model=schemas.FarmOut)
def get_farm(farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    return _to_out(farm)


@router.put("/{farm_id}", response_model=schemas.FarmOut)
def update_farm(
    farm_id: int,
    payload: schemas.FarmUpdate,
    household_id: int = Depends(get_current_household_id),
    household_crop_ids: List[int] = Depends(get_household_crop_ids),
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("crop_id") is not None:
        _ensure_crop_registered(updates["crop_id"], household_crop_ids)
    for key, value in updates.items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return _to_out(farm)


@router.delete("/{farm_id}")
def delete_farm(farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    db.delete(farm)
    db.commit()
    return {"ok": True}
