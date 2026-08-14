from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.database import get_db
from app.deps import get_current_household_id
from app.services.reference_service import to_reference_out

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("", response_model=List[schemas.TreatmentReferenceOut])
def list_my_reference(
    crop_id: Optional[int] = None,
    _household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """농가 앱에서 열람하는 병해충·방제자재 참고자료 (읽기 전용, 활성 항목만).
    선택한 작물(crop_id)에 따라 다른 병해충 목록이 보이는 것을 보여주는 화면에서 사용."""
    query = (
        db.query(models.TreatmentReference)
        .options(selectinload(models.TreatmentReference.materials).selectinload(models.PestDiseaseMaterial.agri_material))
        .filter(models.TreatmentReference.is_active.is_(True))
    )
    if crop_id:
        query = query.filter(models.TreatmentReference.crop_id == crop_id)
    rows = query.order_by(models.TreatmentReference.type, models.TreatmentReference.name_kr).all()
    return [to_reference_out(r) for r in rows]
