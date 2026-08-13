from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/farms", tags=["farms"])


@router.post("", response_model=schemas.FarmOut)
def create_farm(payload: schemas.FarmCreate, db: Session = Depends(get_db)):
    farm = models.Farm(**payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("", response_model=List[schemas.FarmOut])
def list_farms(region: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Farm)
    if region:
        query = query.filter(models.Farm.region == region)
    return query.order_by(models.Farm.created_at.desc()).all()


@router.get("/{farm_id}", response_model=schemas.FarmOut)
def get_farm(farm_id: int, db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    return farm


@router.put("/{farm_id}", response_model=schemas.FarmOut)
def update_farm(farm_id: int, payload: schemas.FarmUpdate, db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/{farm_id}")
def delete_farm(farm_id: int, db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    db.delete(farm)
    db.commit()
    return {"ok": True}
