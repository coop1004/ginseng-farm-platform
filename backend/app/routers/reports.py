import datetime as dt
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.pdf_service import generate_farm_report_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/farms/{farm_id}/pdf")
def download_farm_report(
    farm_id: int,
    start_date: dt.date,
    end_date: dt.date,
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")

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
