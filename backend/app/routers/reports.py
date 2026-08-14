import csv
import datetime as dt
import io
import os
import zipfile
from typing import Optional
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.deps import ensure_farm_access
from app.services.auth_service import decode_access_token
from app.services.pdf_service import generate_farm_report_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _household_id_from_header_or_query(
    authorization: str = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> int:
    """PDF 다운로드는 브라우저/외부 앱으로 바로 열리는 링크라 Authorization 헤더를 못 실어보내는 경우가
    있어, 쿼리스트링의 token도 함께 허용한다."""
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[len("Bearer "):].strip()
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    try:
        user_id = decode_access_token(raw_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")

    membership = db.query(models.HouseholdMember).filter(models.HouseholdMember.user_id == user_id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="소속된 농가가 없습니다.")
    return membership.household_id


@router.get("/farms/{farm_id}/pdf")
def download_farm_report(
    farm_id: int,
    start_date: dt.date,
    end_date: dt.date,
    household_id: int = Depends(_household_id_from_header_or_query),
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)

    work_logs = (
        db.query(models.WorkLog)
        .filter(
            models.WorkLog.farm_id == farm_id,
            models.WorkLog.work_date >= start_date,
            models.WorkLog.work_date <= end_date,
        )
        .order_by(models.WorkLog.work_date)
        .all()
    )
    diagnoses = (
        db.query(models.Diagnosis)
        .filter(
            models.Diagnosis.farm_id == farm_id,
            models.Diagnosis.occurrence_date >= start_date,
            models.Diagnosis.occurrence_date <= end_date,
        )
        .order_by(models.Diagnosis.occurrence_date)
        .all()
    )

    buffer = generate_farm_report_pdf(farm, work_logs, diagnoses, start_date, end_date)
    filename = f"{farm.farm_name}_report_{start_date}_{end_date}.pdf"
    encoded_filename = quote(filename)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"report.pdf\"; filename*=UTF-8''{encoded_filename}"
        },
    )


def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    # Excel(윈도우)에서 한글이 깨지지 않도록 BOM 포함 utf-8-sig 사용
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def _add_photo_if_exists(zf: zipfile.ZipFile, arc_dir: str, photo_path: Optional[str]) -> None:
    if not photo_path:
        return
    full_path = os.path.join(settings.upload_dir, photo_path)
    if os.path.isfile(full_path):
        zf.write(full_path, arcname=f"{arc_dir}/{os.path.basename(photo_path)}")


@router.get("/my-data/export")
def export_my_data(
    household_id: int = Depends(_household_id_from_header_or_query),
    db: Session = Depends(get_db),
):
    """농가 본인의 농장/영농일지/AI진단 기록과 첨부 사진을 CSV+원본 사진이 담긴 ZIP으로 내려받는다.
    개인정보보호법상 정보주체의 자기 데이터 열람/이동권(제35조, 제35조의2)에 대응하기 위한 기능."""
    farms = db.query(models.Farm).filter(models.Farm.household_id == household_id).all()
    farm_ids = [f.id for f in farms]
    farm_name_by_id = {f.id: f.farm_name for f in farms}

    work_logs = (
        db.query(models.WorkLog).filter(models.WorkLog.farm_id.in_(farm_ids)).order_by(models.WorkLog.work_date).all()
        if farm_ids
        else []
    )
    diagnoses = (
        db.query(models.Diagnosis)
        .filter(models.Diagnosis.farm_id.in_(farm_ids))
        .order_by(models.Diagnosis.occurrence_date)
        .all()
        if farm_ids
        else []
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "farms.csv",
            _csv_bytes(
                ["농장ID", "농장명", "작물", "주소", "면적(m2)", "재배형태", "연차/생육단계", "등록일"],
                [
                    [
                        f.id,
                        f.farm_name,
                        f.crop.name_kr if f.crop else "",
                        f.address,
                        f.area_m2,
                        f.facility_type,
                        f.cultivation_year,
                        f.created_at,
                    ]
                    for f in farms
                ],
            ),
        )

        zf.writestr(
            "work_logs.csv",
            _csv_bytes(
                ["기록ID", "농장명", "작업일", "작업면적(m2)", "내용", "등록일"],
                [
                    [w.id, farm_name_by_id.get(w.farm_id, ""), w.work_date, w.work_area_m2, w.content, w.created_at]
                    for w in work_logs
                ],
            ),
        )
        for w in work_logs:
            _add_photo_if_exists(zf, "photos/work_logs", w.photo_path)

        zf.writestr(
            "diagnoses.csv",
            _csv_bytes(
                [
                    "진단ID", "농장명", "작물", "진단유형", "발생일", "AI진단명", "AI확신도",
                    "최종확정명", "최종확정출처", "친환경방제", "화학방제", "등록일",
                ],
                [
                    [
                        d.id,
                        farm_name_by_id.get(d.farm_id, ""),
                        d.crop_name,
                        d.diagnosis_type,
                        d.occurrence_date,
                        d.ai_disease_name,
                        d.ai_confidence,
                        d.final_disease_name,
                        d.final_diagnosis_source,
                        d.eco_treatments_json,
                        d.chemical_treatments_json,
                        d.created_at,
                    ]
                    for d in diagnoses
                ],
            ),
        )
        for d in diagnoses:
            if d.photos:
                for p in d.photos:
                    _add_photo_if_exists(zf, "photos/diagnoses", p.photo_path)
            else:
                _add_photo_if_exists(zf, "photos/diagnoses", d.photo_path)

    zip_buffer.seek(0)
    filename = f"my_data_export_{dt.date.today()}.zip"
    encoded_filename = quote(filename)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=\"export.zip\"; filename*=UTF-8''{encoded_filename}"
        },
    )
