import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_admin

router = APIRouter(prefix="/api/admin/reference", tags=["reference"])


def _to_out(r: models.TreatmentReference) -> dict:
    return {
        "id": r.id,
        "crop_name": r.crop_name,
        "type": r.type,
        "name_kr": r.name_kr,
        "name_en": r.name_en,
        "symptoms": r.symptoms,
        "cause": r.cause,
        "favorable_temp_min": r.favorable_temp_min,
        "favorable_temp_max": r.favorable_temp_max,
        "favorable_humidity_min": r.favorable_humidity_min,
        "favorable_rainfall_note": r.favorable_rainfall_note,
        "eco_treatments": json.loads(r.eco_treatments_json) if r.eco_treatments_json else [],
        "chemical_treatments": json.loads(r.chemical_treatments_json) if r.chemical_treatments_json else [],
        "is_active": r.is_active,
        "updated_by": r.updated_by,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@router.get("", response_model=List[schemas.TreatmentReferenceOut])
def list_references(
    crop_name: Optional[str] = None,
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    query = db.query(models.TreatmentReference)
    if crop_name:
        query = query.filter(models.TreatmentReference.crop_name == crop_name)
    if type:
        query = query.filter(models.TreatmentReference.type == type)
    if is_active is not None:
        query = query.filter(models.TreatmentReference.is_active == is_active)
    rows = query.order_by(models.TreatmentReference.crop_name, models.TreatmentReference.type, models.TreatmentReference.name_kr).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=schemas.TreatmentReferenceOut)
def create_reference(
    payload: schemas.TreatmentReferenceCreate,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    data = payload.model_dump(exclude={"eco_treatments", "chemical_treatments"})
    row = models.TreatmentReference(
        **data,
        eco_treatments_json=json.dumps([t.model_dump() for t in payload.eco_treatments], ensure_ascii=False),
        chemical_treatments_json=json.dumps([t.model_dump() for t in payload.chemical_treatments], ensure_ascii=False),
        updated_by=current_admin.name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.put("/{reference_id}", response_model=schemas.TreatmentReferenceOut)
def update_reference(
    reference_id: int,
    payload: schemas.TreatmentReferenceCreate,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    row = db.query(models.TreatmentReference).filter(models.TreatmentReference.id == reference_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")

    data = payload.model_dump(exclude={"eco_treatments", "chemical_treatments"})
    for key, value in data.items():
        setattr(row, key, value)
    row.eco_treatments_json = json.dumps([t.model_dump() for t in payload.eco_treatments], ensure_ascii=False)
    row.chemical_treatments_json = json.dumps([t.model_dump() for t in payload.chemical_treatments], ensure_ascii=False)
    row.updated_by = current_admin.name
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{reference_id}")
def delete_reference(
    reference_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    row = db.query(models.TreatmentReference).filter(models.TreatmentReference.id == reference_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return {"ok": True}
