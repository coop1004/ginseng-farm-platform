import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id, get_current_user
from app.services.diagnosis_service import add_comment, add_followup, create_diagnosis_record, to_response

router = APIRouter(prefix="/api/diagnoses", tags=["diagnosis"])

# "이어서 기록하기" 후보로 띄울 최근 미해결 진단 판정 기준 - 최초 진단일 또는 가장 최근
# followup 기록일 중 더 나중 것이 이 기간 안이면 "아직 진행 중"으로 본다.
UNRESOLVED_CANDIDATE_WINDOW_DAYS = 14


@router.get("/recent-unresolved", response_model=List[schemas.RecentUnresolvedDiagnosisOut])
def list_recent_unresolved_diagnoses(
    farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    """새 진단 등록 화면 진입 시(사진 촬영 + 농장 선택 직후) 호출 - 이 농장에 최근
    활동이 있었던 진단이 있으면, 그걸 새 진단으로 또 등록할지 아니면 경과 기록만
    이어 붙일지 사용자에게 먼저 물어보기 위한 후보 목록이다."""
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)

    cutoff = dt.datetime.utcnow() - dt.timedelta(days=UNRESOLVED_CANDIDATE_WINDOW_DAYS)
    diagnoses = (
        db.query(models.Diagnosis)
        .filter(models.Diagnosis.farm_id == farm_id)
        .order_by(models.Diagnosis.created_at.desc())
        .limit(30)
        .all()
    )
    candidates = []
    for d in diagnoses:
        last_activity = d.created_at
        for p in d.photos:
            if p.phase == "followup" and p.created_at and p.created_at > last_activity:
                last_activity = p.created_at
        if last_activity >= cutoff:
            candidates.append(
                {
                    "id": d.id,
                    "diagnosis_type": d.diagnosis_type,
                    "disease_name": d.final_disease_name or d.ai_disease_name,
                    "occurrence_date": d.occurrence_date,
                    "last_activity_at": last_activity,
                }
            )
    candidates.sort(key=lambda c: c["last_activity_at"], reverse=True)
    return candidates[:5]


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


@router.post("/{diagnosis_id}/photos", response_model=schemas.DiagnosisPhotoOut)
async def add_diagnosis_followup(
    diagnosis_id: int,
    outcome: str = Form(...),
    note: Optional[str] = Form(None),
    days_since_treatment: Optional[int] = Form(None),
    photo: Optional[UploadFile] = File(None),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """같은 진단에 방제 경과 기록(사진 선택 + 자가평가 필수)을 이어 붙인다. 새
    Diagnosis 레코드를 만들지 않으므로 지역 통계 카운팅에 영향을 주지 않는다."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    try:
        return add_followup(db, d, outcome, note, days_since_treatment, photo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
