"""진단 등록/조회 응답 구성의 공용 로직. 농가 본인이 등록하는 경로(routers/diagnosis.py)와
컨설턴트가 담당 농가를 대신 등록하는 경로(routers/consultant.py)가 사진저장/EXIF/날씨조회/
AI진단 호출까지 동일한 절차를 거치므로, 여기서 한 번만 구현하고 두 라우터가 공유한다."""
import datetime as dt
import json
import os
import uuid
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import exif_service, gemini_service, reference_service, weather_service

LOW_CONFIDENCE_THRESHOLD = 0.6


def determine_status(ai_result: dict) -> str:
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


def save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return filename


def to_response(d: models.Diagnosis) -> dict:
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
        "gps_estimated": d.gps_estimated,
        "photo_taken_at": d.photo_taken_at,
        "photo_taken_at_estimated": d.photo_taken_at_estimated,
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


def build_corrected_reference(db: Session, d: models.Diagnosis) -> Optional[dict]:
    """정정된 진단명(final_disease_name)이 있는 진단에 한해, 마스터 참고자료
    (TreatmentReference)에서 같은 이름의 항목을 찾아 정정된 병명 기준 방제정보를
    별도로 제공한다. ai_disease_name 기준 eco_treatments/chemical_treatments는
    등록 시점 스냅샷이라 정정 후에도 그대로 남아있으므로, 이 함수는 그 값을
    덮어쓰지 않고 화면에 별도 섹션으로 얹을 추가 정보만 반환한다. 매칭되는 항목이
    없으면 None - 호출부(화면)가 폴백 문구로 안내한다."""
    if not d.final_disease_name:
        return None
    crop_id = d.farm.crop_id if d.farm else None
    organization_id = d.farm.organization_id if d.farm else None
    ref = reference_service.find_reference_by_name(db, d.final_disease_name, crop_id)
    if not ref:
        return None
    return reference_service.to_reference_out(ref, organization_id)


async def create_diagnosis_record(
    db: Session,
    farm: models.Farm,
    diagnosis_type: str,
    crop_name_hint: str,
    occurrence_date: Optional[dt.date],
    photos: List[UploadFile],
    created_by_type: str = "household",
    created_by_consultant_id: Optional[int] = None,
) -> models.Diagnosis:
    """사진 저장 -> EXIF 추출 -> 날씨 조회 -> AI 진단 호출 -> Diagnosis(+사진) 저장까지
    전체 등록 절차. 농가 본인 등록(household)과 컨설턴트 현장 등록(consultant) 양쪽에서
    동일하게 쓰인다 - farm 소유/담당 여부 검증은 호출하는 라우터 쪽에서 먼저 끝내고 온다."""
    photos = [p for p in photos if p.filename]
    if not photos:
        raise ValueError("피해 사진을 1장 이상 첨부해주세요.")

    # 클라이언트가 보낸 crop_name(자유 텍스트)은 필터링에 신뢰하지 않는다. 농장에 연결된
    # crop이 진짜 기준이며, 참고자료 필터링(crop_id)과 진단 레코드에 남길 표시 문자열
    # 둘 다 여기서 농장 기준으로 다시 정한다.
    crop_id = farm.crop_id
    resolved_crop_name = farm.crop.name_kr if farm.crop else crop_name_hint

    photo_paths = [save_upload(p) for p in photos]
    full_path = os.path.join(settings.upload_dir, photo_paths[0])
    upload_received_at = dt.datetime.utcnow()

    # 사진 EXIF에 GPS/촬영시각이 없는 경우(카카오톡/문자 전달 사진, 편집본, 위치권한 꺼짐 등)에도
    # 진단 자체는 막히지 않아야 한다 - 아래 순서로 대체하고, 대체가 일어났는지는 별도 플래그로 남겨
    # 진단 상세화면에서 "실제 촬영값이 아님"을 알 수 있게 한다.
    gps_lat, gps_lng, taken_at = exif_service.extract_gps_and_datetime(full_path)
    gps_estimated = False
    if gps_lat is None:
        if farm.latitude is not None and farm.longitude is not None:
            gps_lat, gps_lng = farm.latitude, farm.longitude
            gps_estimated = True
        # 농장 위치도 등록되어 있지 않으면 gps_lat/lng은 None으로 남는다 - 날씨 조회 자체를 생략한다.

    photo_taken_at_estimated = taken_at is None
    weather_query_at = taken_at or upload_received_at
    if photo_taken_at_estimated:
        taken_at = upload_received_at

    if gps_lat is not None and gps_lng is not None:
        weather = await weather_service.get_weather_at(gps_lat, gps_lng, weather_query_at)
    else:
        # 사진에도, 농장 등록 정보에도 위치를 알 근거가 전혀 없다 - 이 경우 계절 추정치 같은
        # 그럴듯한 데모 날씨를 채워넣지 않는다(실제 위치와 무관한 값이 진짜 날씨처럼 보이는
        # 것을 방지). weather_* 필드는 비워두고 화면에서 안내 문구로 보여준다.
        weather = None

    ai_result = gemini_service.diagnose(
        full_path, diagnosis_type, resolved_crop_name, weather or {}, db, crop_id, farm.organization_id
    )

    diagnosis = models.Diagnosis(
        farm_id=farm.id,
        diagnosis_type=diagnosis_type,
        crop_name=resolved_crop_name,
        occurrence_date=occurrence_date or (taken_at.date() if taken_at else dt.date.today()),
        photo_path=photo_paths[0],
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        gps_estimated=gps_estimated,
        photo_taken_at=taken_at,
        photo_taken_at_estimated=photo_taken_at_estimated,
        weather_temp_c=weather.get("temp_c") if weather else None,
        weather_humidity_percent=weather.get("humidity_percent") if weather else None,
        weather_rainfall_mm=weather.get("rainfall_mm") if weather else None,
        weather_wind_ms=weather.get("wind_ms") if weather else None,
        weather_source=weather.get("source") if weather else "unavailable",
        ai_disease_name=ai_result.get("disease_name_kr"),
        ai_disease_name_en=ai_result.get("disease_name_en"),
        ai_symptoms=ai_result.get("symptoms"),
        ai_confidence=ai_result.get("confidence"),
        eco_treatments_json=json.dumps(ai_result.get("eco_treatments", []), ensure_ascii=False),
        chemical_treatments_json=json.dumps(ai_result.get("chemical_treatments", []), ensure_ascii=False),
        ai_raw_response=ai_result.get("_raw"),
        ai_source=ai_result.get("_source"),
        status=determine_status(ai_result),
        created_by_type=created_by_type,
        created_by_consultant_id=created_by_consultant_id,
    )
    db.add(diagnosis)
    db.flush()
    for path in photo_paths:
        db.add(models.DiagnosisPhoto(diagnosis_id=diagnosis.id, photo_path=path))
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


def add_comment(
    db: Session,
    diagnosis: models.Diagnosis,
    author_type: str,
    author_name: str,
    body: str,
    author_user_id: Optional[int] = None,
    author_consultant_id: Optional[int] = None,
) -> models.DiagnosisComment:
    """농가/컨설턴트 양쪽에서 동일한 코멘트 저장 절차를 공유한다 - 진단 1건에
    여러 명이 남기는 스레드이며, 작성자 종류와 무관하게 같은 진단을 보는
    모두에게 노출된다(final_diagnosis_note와 달리 덮어쓰기되지 않음)."""
    comment = models.DiagnosisComment(
        diagnosis_id=diagnosis.id,
        author_type=author_type,
        author_name=author_name,
        author_user_id=author_user_id,
        author_consultant_id=author_consultant_id,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
