import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id, get_current_user
from app.services.diagnosis_service import add_comment, create_diagnosis_record, to_response

router = APIRouter(prefix="/api/diagnoses", tags=["diagnosis"])


@router.post("", response_model=schemas.DiagnosisCreateResponse)
async def create_diagnosis(
    farm_id: int = Form(...),
    diagnosis_type: str = Form(...),  # 병해 / 해충 / 생리장애
    crop_name: str = Form("인삼"),
    occurrence_date: Optional[dt.date] = Form(None),
    photos: List[UploadFile] = File(...),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)

    try:
        diagnosis = await create_diagnosis_record(db, farm, diagnosis_type, crop_name, occurrence_date, photos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return to_response(diagnosis)


@router.get("", response_model=List[schemas.DiagnosisCreateResponse])
def list_diagnoses(
    farm_id: Optional[int] = None,
    diagnosis_type: Optional[str] = None,
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Diagnosis)
        .join(models.Farm, models.Diagnosis.farm_id == models.Farm.id)
        .filter(models.Farm.household_id == household_id)
    )
    if farm_id:
        query = query.filter(models.Diagnosis.farm_id == farm_id)
    if diagnosis_type:
        query = query.filter(models.Diagnosis.diagnosis_type == diagnosis_type)
    if start_date:
        query = query.filter(models.Diagnosis.occurrence_date >= start_date)
    if end_date:
        query = query.filter(models.Diagnosis.occurrence_date <= end_date)
    results = query.order_by(models.Diagnosis.occurrence_date.desc()).all()
    return [to_response(d) for d in results]


@router.get("/{diagnosis_id}", response_model=schemas.DiagnosisCreateResponse)
def get_diagnosis(
    diagnosis_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    return to_response(d)


@router.patch("/{diagnosis_id}/feedback", response_model=schemas.DiagnosisCreateResponse)
def submit_diagnosis_feedback(
    diagnosis_id: int,
    payload: schemas.DiagnosisFeedbackRequest,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """농가가 실제 상황과 AI 진단이 일치했는지 사후 확인한다 (관리자 대시보드의
    'AI 예측 vs 실제 발생 비교' 통계 및 진단 상태 필터에 반영됨)."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    d.farmer_confirmed_correct = payload.correct
    db.commit()
    db.refresh(d)
    return to_response(d)


@router.patch("/{diagnosis_id}/final-diagnosis", response_model=schemas.DiagnosisCreateResponse)
def submit_final_diagnosis(
    diagnosis_id: int,
    payload: schemas.DiagnosisFinalRequest,
    current_user: models.User = Depends(get_current_user),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """AI 진단이 실패했거나(status=분석실패) 확신도가 낮거나, 단순히 AI 결과가
    실제 현장 상황과 다를 때, 농가가 직접 확인한 진단명을 최종 결과로 기록한다.
    이후 처방/통계는 final_disease_name(있으면)을 ai_disease_name보다 우선한다."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    d.final_disease_name = payload.disease_name
    d.final_diagnosis_source = "farmer"
    d.final_diagnosis_note = payload.note
    d.final_diagnosis_by = current_user.name
    d.final_diagnosis_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(d)
    return to_response(d)


@router.get("/{diagnosis_id}/comments", response_model=List[schemas.DiagnosisCommentOut])
def list_diagnosis_comments(
    diagnosis_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    return d.comments


@router.post("/{diagnosis_id}/comments", response_model=schemas.DiagnosisCommentOut)
def create_diagnosis_comment(
    diagnosis_id: int,
    payload: schemas.DiagnosisCommentCreate,
    current_user: models.User = Depends(get_current_user),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """농가 본인이 자신의(또는 컨설턴트가 등록한) 진단에 코멘트를 남긴다.
    누가 등록한 진단이든 같은 농가 소속 농장이면 코멘트를 남길 수 있다."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    return add_comment(db, d, "household", current_user.name, payload.body, author_user_id=current_user.id)


@router.delete("/{diagnosis_id}")
def delete_diagnosis(
    diagnosis_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    db.delete(d)
    db.commit()
    return {"ok": True}
