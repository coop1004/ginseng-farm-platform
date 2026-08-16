"""컨설턴트 활동 통계 계산. 컨설턴트 본인 화면(routers/consultant.py)과 관리자가
특정 컨설턴트 실적을 보는 화면(routers/admin.py) 양쪽이 동일한 집계 로직을 공유한다."""
import datetime as dt

from sqlalchemy.orm import Session

from app import models


def compute_stats(db: Session, consultant: models.ConsultantUser) -> dict:
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
        scoped_diagnoses = (
            db.query(models.Diagnosis)
            .join(models.Farm, models.Diagnosis.farm_id == models.Farm.id)
            .filter(models.Farm.household_id.in_(household_ids))
            .all()
        )

    my_diagnosis_count = sum(1 for d in scoped_diagnoses if d.created_by_consultant_id == consultant.id)
    my_final_diagnosis_count = sum(
        1 for d in scoped_diagnoses if d.final_diagnosis_source == "consultant" and d.final_diagnosis_by == consultant.name
    )
    my_comment_count = (
        db.query(models.DiagnosisComment)
        .filter(models.DiagnosisComment.author_consultant_id == consultant.id)
        .count()
    )
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


def compute_all_consultants_summary(db: Session, top_n: int = 5) -> dict:
    """관리자 대시보드 메인 화면(종합 현황)의 "컨설턴트 활동 실적" 요약 카드용 - 특정
    컨설턴트 한 명이 아니라 전체를 한눈에 보여준다. 개별 상세는 여전히 compute_stats
    (기존 /consultants/{id}/stats)를 그대로 쓴다 - 여기서는 순위를 매기기 위한
    최소 지표(이번 달 진단 건수)만 계산한다."""
    now = dt.datetime.utcnow()
    month_start = dt.datetime(now.year, now.month, 1)

    consultants = db.query(models.ConsultantUser).order_by(models.ConsultantUser.created_at).all()

    diagnosis_count_this_month = 0
    ranking = []
    for consultant in consultants:
        total_count = (
            db.query(models.Diagnosis).filter(models.Diagnosis.created_by_consultant_id == consultant.id).count()
        )
        month_count = (
            db.query(models.Diagnosis)
            .filter(
                models.Diagnosis.created_by_consultant_id == consultant.id,
                models.Diagnosis.created_at >= month_start,
            )
            .count()
        )
        diagnosis_count_this_month += month_count
        ranking.append(
            {
                "consultant_id": consultant.id,
                "name": consultant.name,
                "diagnosis_count_this_month": month_count,
                "total_diagnosis_count": total_count,
            }
        )

    ranking.sort(key=lambda r: r["diagnosis_count_this_month"], reverse=True)

    return {
        "consultant_count": len(consultants),
        "active_consultant_count": sum(1 for c in consultants if c.is_active),
        "diagnosis_count_this_month": diagnosis_count_this_month,
        "ranking": ranking[:top_n],
    }
