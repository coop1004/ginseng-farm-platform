import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id, get_household_crop_ids
from app.seed import get_ginseng_crop_id
from app.services.farm_service import compute_cultivation_year

router = APIRouter(prefix="/api/farms", tags=["farms"])

# 지역 위험 신호등(농가앱 노출용) 집계 기간 - admin.py의 REGIONAL_TREND_WINDOW_DAYS와 같은
# 7일 관례를 따르되, 이웃 농가를 최종 사용자로 노출하는 화면이라 admin 라우터에 결합하지
# 않고 이 파일에서 독립적으로 관리한다.
REGIONAL_RISK_SIGNAL_WINDOW_DAYS = 7

# 농가앱에 노출되는 신호등은 관리자/컨설턴트가 보는 REGIONAL_STATS_MIN_SAMPLE_SIZE(admin.py,
# 내부 관리자 전용이라 1로 사실상 비활성화됨)와 절대 같은 값을 쓰면 안 된다 - 신호등을 보는
# 사람이 접근권 없는 이웃 농가(최종사용자)이기 때문에, 특정 이웃의 발생 사실이 간접적으로도
# 드러나지 않도록 훨씬 보수적인 별도 임계값을 둔다. 동일 병해충명 최다 발생 건수 기준.
FARMER_RISK_CAUTION_MIN_COUNT = 3  # 이 값 이상이면 "주의"
FARMER_RISK_ALERT_MIN_COUNT = 6  # 이 값 이상이면 "경계" (주의보다 우선)


def _to_out(f: models.Farm) -> dict:
    return {
        **{c.name: getattr(f, c.name) for c in f.__table__.columns},
        "household_name": f.household.name if f.household else None,
        "crop_name": f.crop.name_kr if f.crop else None,
        "growth_stage_name": f.growth_stage.name_kr if f.growth_stage else None,
        "cultivation_year_computed": compute_cultivation_year(f.cultivation_start_date, f.cultivation_year),
    }


def _ensure_crop_registered(crop_id: int, household_crop_ids: List[int]) -> None:
    if crop_id not in household_crop_ids:
        raise HTTPException(status_code=403, detail="등록하지 않은 작물로는 농장을 만들 수 없습니다. 먼저 작물을 등록해주세요.")


@router.post("", response_model=schemas.FarmOut)
def create_farm(
    payload: schemas.FarmCreate,
    household_id: int = Depends(get_current_household_id),
    household_crop_ids: List[int] = Depends(get_household_crop_ids),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    if data.get("crop_id") is None:
        # 구버전 모바일 클라이언트(작물 선택 UI 도입 이전)는 crop_id를 안 보낸다 -> 인삼으로 기본값 처리
        data["crop_id"] = get_ginseng_crop_id(db)
    _ensure_crop_registered(data["crop_id"], household_crop_ids)
    farm = models.Farm(household_id=household_id, **data)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return _to_out(farm)


@router.get("", response_model=List[schemas.FarmOut])
def list_farms(household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    # 소프트 삭제된(is_active=False) 농장은 목록에서 제외한다 - 진단/영농일지 이력은
    # 그대로 남아있고, 그쪽 조회 엔드포인트는 이 필터의 영향을 받지 않는다.
    farms = (
        db.query(models.Farm)
        .filter(models.Farm.household_id == household_id, models.Farm.is_active.is_(True))
        .order_by(models.Farm.created_at.desc())
        .all()
    )
    return [_to_out(f) for f in farms]


@router.get("/{farm_id}", response_model=schemas.FarmOut)
def get_farm(farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    return _to_out(farm)


@router.put("/{farm_id}", response_model=schemas.FarmOut)
def update_farm(
    farm_id: int,
    payload: schemas.FarmUpdate,
    household_id: int = Depends(get_current_household_id),
    household_crop_ids: List[int] = Depends(get_household_crop_ids),
    db: Session = Depends(get_db),
):
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("crop_id") is not None:
        _ensure_crop_registered(updates["crop_id"], household_crop_ids)
    # 정식일을 이번 요청에서 직접 수정했다면, 농가가 방금 확인/정정한 실제 값이므로
    # 마이그레이션 근사치 플래그를 해제한다.
    if "cultivation_start_date" in updates:
        farm.cultivation_start_date_estimated = False
    for key, value in updates.items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return _to_out(farm)


@router.delete("/{farm_id}")
def delete_farm(farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    """소프트 삭제 - Farm.diagnoses/work_logs가 cascade delete-orphan으로 걸려 있어
    하드 삭제하면 그 농장의 진단·영농일지 이력이 통째로 사라진다(최근 수정한 지역 통계
    카운팅 로직도 그 이력을 기준으로 계산하므로 영향을 받는다). is_active만 끄고
    실제 행은 보존해, 이력 조회는 그대로 되면서 목록/통계 화면에서만 빠지게 한다."""
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)
    farm.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/{farm_id}/regional-risk-signal")
def get_regional_risk_signal(
    farm_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)
):
    """농가앱 홈 화면용 지역 위험 신호등. admin.py의 regional_stats_breakdown()과 같은
    effective name(final_disease_name 우선, 없으면 ai_disease_name) 집계 방식을 재사용하되,
    이 화면을 보는 사람은 접근권 없는 이웃 농가(최종사용자)이므로 병해충명·정확한 건수·
    농가 수 등은 절대 응답에 포함하지 않고 등급 문자열만 반환한다."""
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_farm_access(farm, household_id)

    if not farm.region:
        return {"level": None}

    # 같은 지역이라도 작물이 다르면 병해충명이 겹쳐도 무관한 정보라, 신호가 이 농가의 작물과
    # 무관한 이웃 작물 발생으로 오염되지 않도록 crop_id까지 함께 좁힌다.
    region_farm_ids = [
        f.id
        for f in db.query(models.Farm)
        .filter(models.Farm.region == farm.region, models.Farm.crop_id == farm.crop_id)
        .all()
    ]
    if not region_farm_ids:
        return {"level": None}

    cutoff = dt.date.today() - dt.timedelta(days=REGIONAL_RISK_SIGNAL_WINDOW_DAYS)
    diagnoses = (
        db.query(models.Diagnosis)
        .filter(
            models.Diagnosis.farm_id.in_(region_farm_ids),
            models.Diagnosis.occurrence_date > cutoff,
            or_(models.Diagnosis.final_disease_name.isnot(None), models.Diagnosis.ai_disease_name.isnot(None)),
        )
        .all()
    )

    # 같은 농장(farm_id)이 같은 병명을 며칠 안에 재등록해도 1건으로만 잡히도록, 진단
    # 레코드 개수가 아니라 "이 병명이 발생한 고유 농장 수"를 센다 - 그래야 한 농장의
    # 반복 재등록이 이웃 농가에게 마치 여러 농장에서 퍼진 것처럼 잘못된 신호를 주지 않는다.
    farm_ids_by_name: dict = {}
    type_by_name: dict = {}
    for d in diagnoses:
        name = d.final_disease_name or d.ai_disease_name
        farm_ids_by_name.setdefault(name, set()).add(d.farm_id)
        type_by_name[name] = d.diagnosis_type

    counts = {name: len(farm_ids) for name, farm_ids in farm_ids_by_name.items()}
    max_count = max(counts.values(), default=0)
    level: Optional[str] = None
    if max_count >= FARMER_RISK_ALERT_MIN_COUNT:
        level = "경계"
    elif max_count >= FARMER_RISK_CAUTION_MIN_COUNT:
        level = "주의"

    # 등급을 만든 병해충의 카테고리(병해/해충/생리장애)만 넘긴다 - 병명 자체나
    # TreatmentReference의 증상·방제자재 문구는 절대 포함하지 않는다. 프런트는 이
    # 값으로 코드에 고정해둔 범용 안내문 중 하나만 골라 보여준다.
    category = type_by_name[max(counts, key=counts.get)] if level is not None else None

    return {"level": level, "category": category}
