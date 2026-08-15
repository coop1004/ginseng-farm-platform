import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import (
    ensure_consultant_farm_access,
    get_consultant_household_ids,
    get_current_consultant,
)
from app.services.auth_service import create_consultant_access_token, verify_password
from app.services.diagnosis_service import create_diagnosis_record, to_response

router = APIRouter(prefix="/api/consultant", tags=["consultant"])


@router.post("/auth/login", response_model=schemas.ConsultantTokenResponse)
def consultant_login(payload: schemas.ConsultantLoginRequest, db: Session = Depends(get_db)):
    consultant = (
        db.query(models.ConsultantUser).filter(models.ConsultantUser.username == payload.username).first()
    )
    if not consultant or not consultant.is_active or not verify_password(payload.password, consultant.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_consultant_access_token(consultant.id)
    return schemas.ConsultantTokenResponse(
        access_token=token, consultant=schemas.ConsultantOut.model_validate(consultant)
    )


@router.get("/auth/me", response_model=schemas.ConsultantOut)
def consultant_me(current_consultant: models.ConsultantUser = Depends(get_current_consultant)):
    return schemas.ConsultantOut.model_validate(current_consultant)


@router.get("/households")
def list_my_households(
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """담당 농가와 그 소속 농장 목록. 시스템 전체 농가가 아니라 배정받은 농가로만
    범위가 제한된다(get_consultant_household_ids)."""
    if not consultant_household_ids:
        return []
    households = db.query(models.Household).filter(models.Household.id.in_(consultant_household_ids)).all()
    result = []
    for h in households:
        farms = db.query(models.Farm).filter(models.Farm.household_id == h.id).all()
        result.append(
            {
                "id": h.id,
                "name": h.name,
                "join_code": h.join_code,
                "farms": [
                    {
                        "id": f.id,
                        "farm_name": f.farm_name,
                        "address": f.address,
                        "region": f.region,
                        "crop_id": f.crop_id,
                        "crop_name": f.crop.name_kr if f.crop else None,
                    }
                    for f in farms
                ],
            }
        )
    return result


@router.get("/diagnoses", response_model=List[schemas.DiagnosisCreateResponse])
def list_consultant_diagnoses(
    household_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    if not consultant_household_ids:
        return []
    query = (
        db.query(models.Diagnosis)
        .join(models.Farm, models.Diagnosis.farm_id == models.Farm.id)
        .filter(models.Farm.household_id.in_(consultant_household_ids))
    )
    if household_id:
        if household_id not in consultant_household_ids:
            raise HTTPException(status_code=403, detail="담당 농가가 아닙니다.")
        query = query.filter(models.Farm.household_id == household_id)
    if farm_id:
        query = query.filter(models.Diagnosis.farm_id == farm_id)
    results = query.order_by(models.Diagnosis.occurrence_date.desc()).all()
    return [to_response(d) for d in results]


@router.get("/diagnoses/{diagnosis_id}", response_model=schemas.DiagnosisCreateResponse)
def get_consultant_diagnosis(
    diagnosis_id: int,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    return to_response(d)


@router.post("/diagnoses", response_model=schemas.DiagnosisCreateResponse)
async def create_consultant_diagnosis(
    farm_id: int = Form(...),
    diagnosis_type: str = Form(...),
    crop_name: str = Form("인삼"),
    occurrence_date: Optional[dt.date] = Form(None),
    photos: List[UploadFile] = File(...),
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 현장 방문 중 담당 농가의 필지에 새 진단을 등록한다. 담당 농가가
    아니면 접근할 수 없고(ensure_consultant_farm_access), 등록된 진단은
    created_by_type="consultant"로 표시되어 농가 쪽 화면에서도 누가 등록했는지
    구분해서 보여줄 수 있다."""
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_consultant_farm_access(farm, consultant_household_ids)

    try:
        diagnosis = await create_diagnosis_record(
            db,
            farm,
            diagnosis_type,
            crop_name,
            occurrence_date,
            photos,
            created_by_type="consultant",
            created_by_consultant_id=current_consultant.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return to_response(diagnosis)


@router.patch("/diagnoses/{diagnosis_id}/final-diagnosis", response_model=schemas.DiagnosisCreateResponse)
def submit_consultant_final_diagnosis(
    diagnosis_id: int,
    payload: schemas.DiagnosisFinalRequest,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가의 진단을 현장 확인 후 정정한다. admin_final_diagnosis와
    동일한 방식이나 final_diagnosis_source가 "consultant"로 남아 누구의 정정인지
    구분된다(농가 본인 정정은 "farmer", 회사 관리자 정정은 "expert")."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    d.final_disease_name = payload.disease_name
    d.final_diagnosis_source = "consultant"
    d.final_diagnosis_note = payload.note
    d.final_diagnosis_by = current_consultant.name
    d.final_diagnosis_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(d)
    return to_response(d)
