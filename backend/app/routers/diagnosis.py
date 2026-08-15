import datetime as dt
import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id, get_current_user
from app.services import exif_service, gemini_service, weather_service

router = APIRouter(prefix="/api/diagnoses", tags=["diagnosis"])

LOW_CONFIDENCE_THRESHOLD = 0.6


def _determine_status(ai_result: dict) -> str:
    """AI 응답의 출처(_source)와 확신도(confidence)를 보고 관리자가 개입해야 하는
    케이스인지 구분한다. gemini_service.diagnose()가 실제 Gemini 호출에 실패하면
    _source가 'demo_fallback'으로 표시되는데(예외를 삼키고 조용히 데모 데이터로
    대체), 이 경우 진단 자체가 신뢰할 수 없으므로 '분석실패'로 남겨 관리자가
    확인하게 한다. 신뢰도가 낮은 경우는 진단은 됐지만 전문가 확인이 필요한
    케이스로 별도 구분한다."""
    if ai_result.get("_source") == "demo_fallback":
        return "분석실패"
    confidence = ai_result.get("confidence")
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        return "전문가검토필요"
    return "분석완료"


def _save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return filename


def _to_response(d: models.Diagnosis) -> dict:
    eco = json.loads(d.eco_treatments_json) if d.eco_treatments_json else []
    chem = json.loads(d.chemical_treatments_json) if d.chemical_treatments_json else []
    return {
        "id": d.id,
        "farm_id": d.farm_id,
        "farm_name": d.farm.farm_name if d.farm else None,
        "diagnosis_type": d.diagnosis_type,
        "crop_name": d.crop_name,
        "occurrence_date": d.occurrence_date,
        "photo_path": d.photo_path,
        "photo_paths": [p.photo_path for p in d.photos] if d.photos else ([d.photo_path] if d.photo_path else []),
        "gps_lat": d.gps_lat,
        "gps_lng": d.gps_lng,
        "photo_taken_at": d.photo_taken_at,
        "weather_temp_c": d.weather_temp_c,
        "weather_humidity_percent": d.weather_humidity_percent,
        "weather_rainfall_mm": d.weather_rainfall_mm,
        "weather_wind_ms": d.weather_wind_ms,
        "weather_source": d.weather_source,
        "ai_disease_name": d.ai_disease_name,
        "ai_disease_name_en": d.ai_disease_name_en,
        "ai_symptoms": d.ai_symptoms,
        "ai_confidence": d.ai_confidence,
        "eco_treatments": eco,
        "chemical_treatments": chem,
        "ai_source": d.ai_source,
        "status": d.status,
        "farmer_confirmed_correct": d.farmer_confirmed_correct,
        "final_disease_name": d.final_disease_name,
        "final_diagnosis_source": d.final_diagnosis_source,
        "final_diagnosis_note": d.final_diagnosis_note,
        "final_diagnosis_by": d.final_diagnosis_by,
        "final_diagnosis_at": d.final_diagnosis_at,
        "crop_is_sample_data": bool(d.farm.crop.is_sample_data) if d.farm and d.farm.crop else False,
        "created_by_type": d.created_by_type,
        "created_by_consultant_name": d.created_by_consultant.name if d.created_by_consultant else None,
        "created_at": d.created_at,
    }


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

    photos = [p for p in photos if p.filename]
    if not photos:
        raise HTTPException(status_code=400, detail="피해 사진을 1장 이상 첨부해주세요.")

    # 모바일이 보낸 crop_name(자유 텍스트)은 필터링에 신뢰하지 않는다. 농장에 연결된
    # crop이 진짜 기준이며, 참고자료 필터링(crop_id)과 진단 레코드에 남길 표시 문자열
    # 둘 다 여기서 농장 기준으로 다시 정한다.
    crop_id = farm.crop_id
    resolved_crop_name = farm.crop.name_kr if farm.crop else crop_name

    photo_paths = [_save_upload(p) for p in photos]
    full_path = os.path.join(settings.upload_dir, photo_paths[0])

    gps_lat, gps_lng, taken_at = exif_service.extract_gps_and_datetime(full_path)
    if gps_lat is None:
        gps_lat, gps_lng = farm.latitude, farm.longitude

    weather = await weather_service.get_weather_at(gps_lat, gps_lng, taken_at)

    ai_result = gemini_service.diagnose(full_path, diagnosis_type, resolved_crop_name, weather, db, crop_id)

    diagnosis = models.Diagnosis(
        farm_id=farm_id,
        diagnosis_type=diagnosis_type,
        crop_name=resolved_crop_name,
        occurrence_date=occurrence_date or (taken_at.date() if taken_at else dt.date.today()),
        photo_path=photo_paths[0],
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        photo_taken_at=taken_at,
        weather_temp_c=weather.get("temp_c"),
        weather_humidity_percent=weather.get("humidity_percent"),
        weather_rainfall_mm=weather.get("rainfall_mm"),
        weather_wind_ms=weather.get("wind_ms"),
        weather_source=weather.get("source"),
        ai_disease_name=ai_result.get("disease_name_kr"),
        ai_disease_name_en=ai_result.get("disease_name_en"),
        ai_symptoms=ai_result.get("symptoms"),
        ai_confidence=ai_result.get("confidence"),
        eco_treatments_json=json.dumps(ai_result.get("eco_treatments", []), ensure_ascii=False),
        chemical_treatments_json=json.dumps(ai_result.get("chemical_treatments", []), ensure_ascii=False),
        ai_raw_response=ai_result.get("_raw"),
        ai_source=ai_result.get("_source"),
        status=_determine_status(ai_result),
    )
    db.add(diagnosis)
    db.flush()
    for path in photo_paths:
        db.add(models.DiagnosisPhoto(diagnosis_id=diagnosis.id, photo_path=path))
    db.commit()
    db.refresh(diagnosis)
    return _to_response(diagnosis)


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
    return [_to_response(d) for d in results]


@router.get("/{diagnosis_id}", response_model=schemas.DiagnosisCreateResponse)
def get_diagnosis(
    diagnosis_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(d.farm, household_id)
    return _to_response(d)


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
    return _to_response(d)


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
    return _to_response(d)


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
