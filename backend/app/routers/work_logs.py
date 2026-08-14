import datetime as dt
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id

router = APIRouter(prefix="/api/work-logs", tags=["work_logs"])


def _save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return filename


def _to_out(w: models.WorkLog) -> dict:
    return {
        "id": w.id,
        "farm_id": w.farm_id,
        "work_date": w.work_date,
        "work_area_m2": w.work_area_m2,
        "content": w.content,
        "photo_path": w.photo_path,
        "created_at": w.created_at,
        "farm_name": w.farm.farm_name if w.farm else None,
    }


def _get_owned_farm(db: Session, farm_id: int, household_id: int) -> models.Farm:
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    return farm


@router.post("", response_model=schemas.WorkLogOut)
def create_work_log(
    farm_id: int = Form(...),
    work_date: Optional[dt.date] = Form(None),
    work_area_m2: float = Form(0),
    content: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    farm = _get_owned_farm(db, farm_id, household_id)

    photo_path = _save_upload(photo) if photo and photo.filename else None

    work_log = models.WorkLog(
        farm_id=farm_id,
        work_date=work_date or dt.date.today(),
        work_area_m2=work_area_m2 or farm.area_m2,
        content=content,
        photo_path=photo_path,
    )
    db.add(work_log)
    db.commit()
    db.refresh(work_log)
    return _to_out(work_log)


@router.get("", response_model=List[schemas.WorkLogOut])
def list_work_logs(
    farm_id: Optional[int] = None,
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.WorkLog)
        .join(models.Farm, models.WorkLog.farm_id == models.Farm.id)
        .filter(models.Farm.household_id == household_id)
    )
    if farm_id:
        query = query.filter(models.WorkLog.farm_id == farm_id)
    if start_date:
        query = query.filter(models.WorkLog.work_date >= start_date)
    if end_date:
        query = query.filter(models.WorkLog.work_date <= end_date)
    logs = query.order_by(models.WorkLog.work_date.desc()).all()
    return [_to_out(w) for w in logs]


@router.get("/{log_id}", response_model=schemas.WorkLogOut)
def get_work_log(log_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    w = db.query(models.WorkLog).filter(models.WorkLog.id == log_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="작업일지를 찾을 수 없습니다.")
    ensure_farm_access(w.farm, household_id)
    return _to_out(w)


@router.delete("/{log_id}")
def delete_work_log(log_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    w = db.query(models.WorkLog).filter(models.WorkLog.id == log_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="작업일지를 찾을 수 없습니다.")
    ensure_farm_access(w.farm, household_id)
    db.delete(w)
    db.commit()
    return {"ok": True}
