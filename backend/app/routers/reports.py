import datetime as dt
from typing import Optional
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models
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
