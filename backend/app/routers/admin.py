import datetime as dt
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_admin
from app.routers.stats import build_summary
from app.services.auth_service import create_admin_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/auth/login", response_model=schemas.AdminTokenResponse)
def admin_login(payload: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_admin_access_token(admin.id)
    return schemas.AdminTokenResponse(access_token=token, admin=schemas.AdminUserOut.model_validate(admin))


@router.get("/auth/me", response_model=schemas.AdminUserOut)
def admin_me(current_admin: models.AdminUser = Depends(get_current_admin)):
    return schemas.AdminUserOut.model_validate(current_admin)


@router.post("/auth/change-password")
def admin_change_password(
    payload: schemas.AdminChangePasswordRequest,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    if not verify_password(payload.current_password, current_admin.password_hash):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="새 비밀번호는 8자 이상이어야 합니다.")
    current_admin.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.post("/auth/register", response_model=schemas.AdminUserOut)
def admin_register(
    payload: schemas.AdminRegisterRequest,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """신규 관리자 계정 추가. 이미 로그인된 관리자만 다른 관리자를 추가로 등록할 수 있다
    (누구나 가입 가능한 공개 가입 절차가 아님 - 사내 담당자 전용)."""
    if db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")
    admin = models.AdminUser(
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return schemas.AdminUserOut.model_validate(admin)


@router.get("/auth/list", response_model=List[schemas.AdminUserOut])
def admin_list(db: Session = Depends(get_db), _current_admin: models.AdminUser = Depends(get_current_admin)):
    return db.query(models.AdminUser).order_by(models.AdminUser.created_at).all()


@router.delete("/auth/{admin_id}")
def admin_delete(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    if admin_id == current_admin.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다.")
    target = db.query(models.AdminUser).filter(models.AdminUser.id == admin_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="관리자를 찾을 수 없습니다.")
    if db.query(models.AdminUser).count() <= 1:
        raise HTTPException(status_code=400, detail="마지막 남은 관리자 계정은 삭제할 수 없습니다.")
    db.delete(target)
    db.commit()
    return {"ok": True}


@router.get("/stats/summary", response_model=schemas.StatsSummary)
def admin_stats_summary(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """관리자 대시보드용 전사(全社) 통계 - 특정 농가로 필터링하지 않고 전체 집계."""
    summary = build_summary(db.query(models.Farm), db.query(models.WorkLog), db.query(models.Diagnosis))
    summary["total_households"] = db.query(models.Household).count()
    return summary


@router.get("/farms/overview")
def farms_overview(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """농가별 최근 활동 요약: 관리자 대시보드 메인 테이블용."""
    farms = db.query(models.Farm).all()
    result = []
    for farm in farms:
        last_diag = (
            db.query(models.Diagnosis)
            .filter(models.Diagnosis.farm_id == farm.id)
            .order_by(models.Diagnosis.occurrence_date.desc())
            .first()
        )
        last_work = (
            db.query(models.WorkLog)
            .filter(models.WorkLog.farm_id == farm.id)
            .order_by(models.WorkLog.work_date.desc())
            .first()
        )
        diag_count_30d = (
            db.query(models.Diagnosis)
            .filter(
                models.Diagnosis.farm_id == farm.id,
                models.Diagnosis.occurrence_date >= dt.date.today() - dt.timedelta(days=30),
            )
            .count()
        )
        result.append(
            {
                "farm_id": farm.id,
                "farm_name": farm.farm_name,
                "household_id": farm.household_id,
                "household_name": farm.household.name if farm.household else None,
                "region": farm.region,
                "address": farm.address,
                "latitude": farm.latitude,
                "longitude": farm.longitude,
                "facility_type": farm.facility_type,
                "cultivation_year": farm.cultivation_year,
                "area_m2": farm.area_m2,
                "last_diagnosis": {
                    "id": last_diag.id,
                    "type": last_diag.diagnosis_type,
                    "name": last_diag.ai_disease_name,
                    "date": last_diag.occurrence_date,
                    "confidence": last_diag.ai_confidence,
                }
                if last_diag
                else None,
                "last_work_log_date": last_work.work_date if last_work else None,
                "diagnosis_count_30d": diag_count_30d,
                "risk_level": "높음" if diag_count_30d >= 3 else ("보통" if diag_count_30d >= 1 else "낮음"),
            }
        )
    result.sort(key=lambda x: x["diagnosis_count_30d"], reverse=True)
    return result


@router.get("/regional-stats")
def regional_stats(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """지역별 병해충 발생 현황: 지도/차트용 집계."""
    farms = {f.id: f for f in db.query(models.Farm).all()}
    diagnoses = db.query(models.Diagnosis).all()

    region_data: dict = {}
    for d in diagnoses:
        farm = farms.get(d.farm_id)
        if not farm or not farm.region:
            continue
        region = farm.region
        if region not in region_data:
            region_data[region] = {
                "region": region,
                "latitude": farm.latitude,
                "longitude": farm.longitude,
                "total": 0,
                "by_type": Counter(),
                "by_name": Counter(),
            }
        region_data[region]["total"] += 1
        region_data[region]["by_type"][d.diagnosis_type] += 1
        if d.ai_disease_name:
            region_data[region]["by_name"][d.ai_disease_name] += 1

    output = []
    for region, data in region_data.items():
        output.append(
            {
                "region": region,
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "total": data["total"],
                "by_type": dict(data["by_type"]),
                "top_issue": data["by_name"].most_common(1)[0][0] if data["by_name"] else None,
            }
        )
    output.sort(key=lambda x: x["total"], reverse=True)
    return output


@router.get("/feed")
def recent_activity_feed(
    limit: int = 20, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """최근 발생 진단 실시간 피드."""
    diagnoses = (
        db.query(models.Diagnosis)
        .order_by(models.Diagnosis.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": d.id,
            "farm_id": d.farm_id,
            "farm_name": d.farm.farm_name if d.farm else None,
            "region": d.farm.region if d.farm else None,
            "diagnosis_type": d.diagnosis_type,
            "ai_disease_name": d.ai_disease_name,
            "confidence": d.ai_confidence,
            "occurrence_date": d.occurrence_date,
            "created_at": d.created_at,
        }
        for d in diagnoses
    ]


@router.post("/notifications", response_model=schemas.NotificationOut)
def send_notification(
    payload: schemas.NotificationCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """농가에 친환경 자재 처방 알림 전송 (시뮬레이션 - DB 저장 후 모바일 앱에서 조회 가능)."""
    farm = db.query(models.Farm).filter(models.Farm.id == payload.farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")

    notification = models.Notification(**payload.model_dump())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    out = schemas.NotificationOut.model_validate(notification)
    out.farm_name = farm.farm_name
    return out


@router.get("/notifications", response_model=List[schemas.NotificationOut])
def list_notifications(
    farm_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    query = db.query(models.Notification)
    if farm_id:
        query = query.filter(models.Notification.farm_id == farm_id)
    notifications = query.order_by(models.Notification.created_at.desc()).all()
    results = []
    for n in notifications:
        out = schemas.NotificationOut.model_validate(n)
        out.farm_name = n.farm.farm_name if n.farm else None
        results.append(out)
    return results
