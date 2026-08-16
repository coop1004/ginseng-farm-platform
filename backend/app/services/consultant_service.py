"""컨설턴트 활동 통계 계산. 컨설턴트 본인 화면(routers/consultant.py)과 관리자가
컨설턴트 실적을 보는 화면(routers/admin.py - 메인 요약 카드 + 컨설턴트 활동현황
전용 화면) 양쪽이 동일한 집계 로직을 공유한다."""
import datetime as dt
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models


def resolve_period_range(
    period: str = "all",
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    """기간 프리셋 또는 사용자 지정 시작/종료일을 (start, end) datetime 범위로 바꾼다.
    start_date/end_date가 하나라도 있으면 그걸 우선한다(period 값은 무시) - 사용자가
    직접 고른 기간이 프리셋보다 항상 더 구체적인 의도이기 때문. 없으면 period 프리셋으로
    계산하고, "all"이거나 알 수 없는 값이면 (None, None)으로 무제한을 뜻한다."""
    if start_date or end_date:
        start = dt.datetime.combine(start_date, dt.time.min) if start_date else None
        end = dt.datetime.combine(end_date, dt.time.max) if end_date else None
        return start, end

    now = dt.datetime.utcnow()
    if period == "this_month":
        return dt.datetime(now.year, now.month, 1), None
    if period == "last_month":
        first_this_month = dt.datetime(now.year, now.month, 1)
        prev_month = 12 if now.month == 1 else now.month - 1
        prev_year = now.year - 1 if now.month == 1 else now.year
        return dt.datetime(prev_year, prev_month, 1), first_this_month - dt.timedelta(microseconds=1)
    if period == "last_3_months":
        return now - dt.timedelta(days=90), None
    if period == "this_year":
        return dt.datetime(now.year, 1, 1), None
    return None, None  # "all" 또는 알 수 없는 값


def compute_stats(
    db: Session,
    consultant: models.ConsultantUser,
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
) -> dict:
    """담당 농가/농장 수(household_count/farm_count)는 "지금 배정된 범위"라는 개념이라
    기간과 무관하게 항상 현재 값을 쓴다. 나머지(진단·코멘트·피드백 건수)는 start/end
    안에서 발생한 것만 센다 - 기본값(None, None)이면 기존과 동일하게 전체 기간이다."""
    household_ids = [
        r[0]
        for r in db.query(models.ConsultantHousehold.household_id)
        .filter(models.ConsultantHousehold.consultant_id == consultant.id)
        .all()
    ]

    household_count = len(household_ids)
    farm_count = 0
    scoped_diagnoses: list[models.Diagnosis] = []
    if household_ids:
        farm_count = db.query(models.Farm).filter(models.Farm.household_id.in_(household_ids)).count()
        diagnoses_query = (
            db.query(models.Diagnosis)
            .join(models.Farm, models.Diagnosis.farm_id == models.Farm.id)
            .filter(models.Farm.household_id.in_(household_ids))
        )
        if start is not None:
            diagnoses_query = diagnoses_query.filter(models.Diagnosis.created_at >= start)
        if end is not None:
            diagnoses_query = diagnoses_query.filter(models.Diagnosis.created_at <= end)
        scoped_diagnoses = diagnoses_query.all()

    my_diagnosis_count = sum(1 for d in scoped_diagnoses if d.created_by_consultant_id == consultant.id)
    my_final_diagnosis_count = sum(
        1 for d in scoped_diagnoses if d.final_diagnosis_source == "consultant" and d.final_diagnosis_by == consultant.name
    )

    comment_query = db.query(models.DiagnosisComment).filter(
        models.DiagnosisComment.author_consultant_id == consultant.id
    )
    if start is not None:
        comment_query = comment_query.filter(models.DiagnosisComment.created_at >= start)
    if end is not None:
        comment_query = comment_query.filter(models.DiagnosisComment.created_at <= end)
    my_comment_count = comment_query.count()

    farmer_feedback_correct = sum(1 for d in scoped_diagnoses if d.farmer_confirmed_correct is True)
    farmer_feedback_incorrect = sum(1 for d in scoped_diagnoses if d.farmer_confirmed_correct is False)
    farmer_feedback_pending = sum(1 for d in scoped_diagnoses if d.farmer_confirmed_correct is None)

    return {
        "household_count": household_count,
        "farm_count": farm_count,
        "total_diagnosis_count": len(scoped_diagnoses),
        "my_diagnosis_count": my_diagnosis_count,
        "my_final_diagnosis_count": my_final_diagnosis_count,
        "my_comment_count": my_comment_count,
        "farmer_feedback_correct": farmer_feedback_correct,
        "farmer_feedback_incorrect": farmer_feedback_incorrect,
        "farmer_feedback_pending": farmer_feedback_pending,
    }


def compute_all_consultants_summary(
    db: Session,
    top_n: int = 5,
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
) -> dict:
    """관리자 대시보드 메인 화면 "컨설턴트 활동 실적" 요약 카드와 "컨설턴트 활동현황"
    전용 화면이 공유하는 집계 엔드포인트용 함수. top_n으로 상위 몇 명만 자를지
    정하고(메인 카드는 5, 전용 화면 "전체 보기"는 충분히 큰 값을 넘겨 사실상 전체),
    start/end로 기간을 제한한다(둘 다 None이면 무제한 = 전체 기간)."""
    consultants = db.query(models.ConsultantUser).order_by(models.ConsultantUser.created_at).all()

    diagnosis_count_total = 0
    ranking: List[dict] = []
    for consultant in consultants:
        total_all_time = (
            db.query(models.Diagnosis).filter(models.Diagnosis.created_by_consultant_id == consultant.id).count()
        )

        diag_query = db.query(models.Diagnosis).filter(models.Diagnosis.created_by_consultant_id == consultant.id)
        if start is not None:
            diag_query = diag_query.filter(models.Diagnosis.created_at >= start)
        if end is not None:
            diag_query = diag_query.filter(models.Diagnosis.created_at <= end)
        period_diagnoses = diag_query.all()
        diagnosis_count = len(period_diagnoses)

        final_diagnosis_count = sum(
            1
            for d in period_diagnoses
            if d.final_diagnosis_source == "consultant" and d.final_diagnosis_by == consultant.name
        )

        comment_query = db.query(models.DiagnosisComment).filter(
            models.DiagnosisComment.author_consultant_id == consultant.id
        )
        if start is not None:
            comment_query = comment_query.filter(models.DiagnosisComment.created_at >= start)
        if end is not None:
            comment_query = comment_query.filter(models.DiagnosisComment.created_at <= end)
        comment_count = comment_query.count()

        feedback_correct = sum(1 for d in period_diagnoses if d.farmer_confirmed_correct is True)
        feedback_incorrect = sum(1 for d in period_diagnoses if d.farmer_confirmed_correct is False)
        feedback_total = feedback_correct + feedback_incorrect
        feedback_accuracy_percent = round(feedback_correct / feedback_total * 100, 1) if feedback_total else None

        diagnosis_count_total += diagnosis_count
        ranking.append(
            {
                "consultant_id": consultant.id,
                "name": consultant.name,
                "diagnosis_count": diagnosis_count,
                "comment_count": comment_count,
                "final_diagnosis_count": final_diagnosis_count,
                "feedback_correct": feedback_correct,
                "feedback_incorrect": feedback_incorrect,
                "feedback_accuracy_percent": feedback_accuracy_percent,
                "total_diagnosis_count": total_all_time,
            }
        )

    ranking.sort(key=lambda r: r["diagnosis_count"], reverse=True)

    return {
        "consultant_count": len(consultants),
        "active_consultant_count": sum(1 for c in consultants if c.is_active),
        "diagnosis_count": diagnosis_count_total,
        "ranking": ranking[:top_n],
    }
