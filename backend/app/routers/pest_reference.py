from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.database import get_db
from app.deps import get_household_crop_ids
from app.services.reference_service import to_reference_out

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("", response_model=List[schemas.TreatmentReferenceOut])
def list_my_reference(
    crop_id: Optional[int] = None,
    household_crop_ids: List[int] = Depends(get_household_crop_ids),
    db: Session = Depends(get_db),
):
    """농가 앱에서 열람하는 병해충·방제자재 참고자료 (읽기 전용, 활성 항목만). 로그인한
    농가가 등록한 작물 범위 밖은 조회할 수 없다 — crop_id를 지정하면 등록 목록에 있는지
    확인하고(없으면 403), 생략하면 "전체"가 아니라 등록한 작물 전체로 필터링한다."""
    if crop_id is not None and crop_id not in household_crop_ids:
        raise HTTPException(status_code=403, detail="등록하지 않은 작물의 자료는 조회할 수 없습니다.")

    query = (
        db.query(models.TreatmentReference)
        .options(selectinload(models.TreatmentReference.materials).selectinload(models.PestDiseaseMaterial.agri_material))
        .filter(models.TreatmentReference.is_active.is_(True))
    )
    if crop_id is not None:
        query = query.filter(models.TreatmentReference.crop_id == crop_id)
    else:
        query = query.filter(models.TreatmentReference.crop_id.in_(household_crop_ids))
    rows = query.order_by(models.TreatmentReference.type, models.TreatmentReference.name_kr).all()
    return [to_reference_out(r) for r in rows]
