from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.database import get_db
from app.deps import get_current_admin
from app.services.reference_service import build_treatment_lists, sync_pest_disease_materials

router = APIRouter(prefix="/api/admin/reference", tags=["reference"])


def _to_out(r: models.TreatmentReference) -> dict:
    eco, chemical = build_treatment_lists(r)
    return {
        "id": r.id,
        "crop_id": r.crop_id,
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
        "photo_path": r.photo_path,
        "is_sample_data": r.is_sample_data,
        "eco_treatments": eco,
        "chemical_treatments": chemical,
        "is_active": r.is_active,
        "updated_by": r.updated_by,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _resolve_crop_name(db: Session, crop_id: int) -> str:
    crop = db.query(models.Crop).filter(models.Crop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=400, detail="존재하지 않는 작물입니다.")
    return crop.name_kr


@router.get("", response_model=List[schemas.TreatmentReferenceOut])
def list_references(
    crop_id: Optional[int] = None,
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    query = db.query(models.TreatmentReference).options(
        selectinload(models.TreatmentReference.materials).selectinload(models.PestDiseaseMaterial.agri_material)
    )
    if crop_id:
        query = query.filter(models.TreatmentReference.crop_id == crop_id)
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
    crop_name = _resolve_crop_name(db, payload.crop_id)
    data = payload.model_dump(exclude={"eco_treatments", "chemical_treatments"})
    row = models.TreatmentReference(**data, crop_name=crop_name, updated_by=current_admin.name)
    db.add(row)
    db.flush()

    sync_pest_disease_materials(
        db, row, [t.model_dump() for t in payload.eco_treatments], [t.model_dump() for t in payload.chemical_treatments]
    )
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

    crop_name = _resolve_crop_name(db, payload.crop_id)
    data = payload.model_dump(exclude={"eco_treatments", "chemical_treatments"})
    for key, value in data.items():
        setattr(row, key, value)
    row.crop_name = crop_name
    row.updated_by = current_admin.name
    db.flush()

    sync_pest_disease_materials(
        db, row, [t.model_dump() for t in payload.eco_treatments], [t.model_dump() for t in payload.chemical_treatments]
    )
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


@router.get("/agri-materials", response_model=List[schemas.AgriMaterialOut])
def list_agri_materials(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """CMS 자재 입력란의 자동완성(datalist)용 — 기존에 등록된 자재 목록."""
    return (
        db.query(models.AgriMaterial)
        .filter(models.AgriMaterial.is_active.is_(True))
        .order_by(models.AgriMaterial.name)
        .all()
    )
