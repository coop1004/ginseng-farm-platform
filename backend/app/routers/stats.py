import datetime as dt
from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Query, Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_household_id

router = APIRouter(prefix="/api/stats", tags=["stats"])


def build_summary(farm_query: Query, work_query: Query, diag_query: Query) -> dict:
    """농가 범위(내 필지) 또는 전사 범위(관리자, 전체 필지) 양쪽에서 재사용하는 통계 집계 로직."""
    diagnoses = diag_query.all()

    diagnoses_by_type = Counter(d.diagnosis_type for d in diagnoses)
    pest_counter = Counter(d.ai_disease_name for d in diagnoses if d.ai_disease_name)
    top_pests = [{"name": name, "count": count} for name, count in pest_counter.most_common(5)]

    monthly_counter: Counter = Counter()
    for d in diagnoses:
        if d.occurrence_date:
            key = d.occurrence_date.strftime("%Y-%m")
            monthly_counter[key] += 1
    monthly = [{"month": k, "count": v} for k, v in sorted(monthly_counter.items())]

    farm_counter: Counter = Counter()
    farm_names = {}
    for d in diagnoses:
        farm_counter[d.farm_id] += 1
        if d.farm_id not in farm_names and d.farm:
            farm_names[d.farm_id] = d.farm.farm_name
    diagnoses_by_farm = [
        {"farm_id": fid, "farm_name": farm_names.get(fid, f"농장#{fid}"), "count": c}
        for fid, c in farm_counter.most_common()
    ]

    confirmed = [d for d in diagnoses if d.farmer_confirmed_correct is not None]
    correct = sum(1 for d in confirmed if d.farmer_confirmed_correct)
    ai_vs_actual = {
        "total_feedback": len(confirmed),
        "correct": correct,
        "incorrect": len(confirmed) - correct,
        "accuracy_percent": round((correct / len(confirmed)) * 100, 1) if confirmed else None,
    }

    return {
        "total_farms": farm_query.count(),
        "total_work_logs": work_query.count(),
        "total_diagnoses": len(diagnoses),
        "diagnoses_by_type": dict(diagnoses_by_type),
        "top_pests": top_pests,
        "monthly_diagnoses": monthly,
        "diagnoses_by_farm": diagnoses_by_farm,
        "ai_vs_actual": ai_vs_actual,
    }


@router.get("/summary", response_model=schemas.StatsSummary)
def get_summary(
    farm_id: Optional[int] = None,
    crop_id: Optional[int] = None,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """crop_id를 주면 홈 화면 요약을 그 작물의 필지로만 좁힌다 — 모바일이 현재 활성 작물
    기준으로 대시보드를 보여줄 때 사용. 등록 여부 검증은 하지 않는다(단순 조회 필터라
    다른 작물 crop_id를 넣어도 그 작물 소속 필지가 없으면 0건으로 나올 뿐 정보 노출이 없음)."""
    farm_query = db.query(models.Farm).filter(models.Farm.household_id == household_id)
    work_query = db.query(models.WorkLog).join(models.Farm).filter(models.Farm.household_id == household_id)
    diag_query = db.query(models.Diagnosis).join(models.Farm).filter(models.Farm.household_id == household_id)

    if crop_id:
        farm_query = farm_query.filter(models.Farm.crop_id == crop_id)
        work_query = work_query.filter(models.Farm.crop_id == crop_id)
        diag_query = diag_query.filter(models.Farm.crop_id == crop_id)

    if farm_id:
        work_query = work_query.filter(models.WorkLog.farm_id == farm_id)
        diag_query = diag_query.filter(models.Diagnosis.farm_id == farm_id)

    return build_summary(farm_query, work_query, diag_query)


@router.get("/calendar")
def get_calendar(
    farm_id: Optional[int] = None,
    year: int = dt.date.today().year,
    month: int = dt.date.today().month,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """캘린더 뷰용: 해당 월의 날짜별 작업일지/진단 건수."""
    start = dt.date(year, month, 1)
    end = dt.date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)

    work_query = (
        db.query(models.WorkLog)
        .join(models.Farm)
        .filter(models.Farm.household_id == household_id, models.WorkLog.work_date >= start, models.WorkLog.work_date < end)
    )
    diag_query = (
        db.query(models.Diagnosis)
        .join(models.Farm)
        .filter(
            models.Farm.household_id == household_id,
            models.Diagnosis.occurrence_date >= start,
            models.Diagnosis.occurrence_date < end,
        )
    )
    if farm_id:
        work_query = work_query.filter(models.WorkLog.farm_id == farm_id)
        diag_query = diag_query.filter(models.Diagnosis.farm_id == farm_id)

    day_map = defaultdict(lambda: {"work_logs": 0, "diagnoses": 0})
    for w in work_query.all():
        day_map[w.work_date.isoformat()]["work_logs"] += 1
    for d in diag_query.all():
        day_map[d.occurrence_date.isoformat()]["diagnoses"] += 1

    return [{"date": k, **v} for k, v in sorted(day_map.items())]
