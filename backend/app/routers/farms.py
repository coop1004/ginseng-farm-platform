from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id

router = APIRouter(prefix="/api/farms", tags=["farms"])


def _to_out(f: models.Farm) -> dict:
    return {
        **{c.name: getattr(f, c.name) for c in f.__table__.columns},
        "household_name": f.household.name if f.household else None,
    }


@router.post("", response_model=schemas.FarmOut)
def create_farm(
    payload: schemas.FarmCreate,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    farm = models.Farm(household_id=household_id, **payload.model_dump())
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
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
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
