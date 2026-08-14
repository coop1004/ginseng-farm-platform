"""3단계(지역 통계 대시보드 프로토타입) 데모용 시드.

기존 인삼 데모 농가(seed.py)는 이미 6개 지역에 걸쳐 실제와 유사한 진단/작업 기록을
갖고 있다. 하지만 고추/배추(파일럿 작물)는 2단계에서 병해충 참고자료만 등록됐을 뿐,
실제 농장/진단 기록이 하나도 없어 관리자 대시보드의 지역별 발생 지도·통계에 인삼만
나타난다. 이 모듈은 같은 지역 5곳에 고추/배추 샘플 농장+진단 기록을 추가해서
"지역 x 작물" 비교가 실제로 동작하는 걸 보여준다. 전부 실제 농가 데이터가 아니라
가상 시연 데이터이므로 농가/농장명에 "[샘플]"을 명시한다.
"""
import datetime as dt
import json
import random

from sqlalchemy.orm import Session

from app import models
from app.services.auth_service import hash_password
from app.services.reference_service import build_treatment_lists

REGIONAL_DEMO_REGIONS = [
    dict(region="금산", latitude=36.1088, longitude=127.4880, address="충청남도 금산군 제원면"),
    dict(region="풍기", latitude=36.8592, longitude=128.5219, address="경상북도 영주시 풍기읍"),
    dict(region="강화", latitude=37.6975, longitude=126.4467, address="인천광역시 강화군 불은면"),
    dict(region="진안", latitude=35.7917, longitude=127.4247, address="전라북도 진안군 진안읍"),
    dict(region="장수", latitude=35.6474, longitude=127.5209, address="전라북도 장수군 장수읍"),
]

DEMO_PILOT_CROPS = ["고추", "배추"]
DEMO_PASSWORD = "farm1234"


def _marker_household_name(crop_name: str) -> str:
    return f"[샘플] {crop_name} 지역통계 시연"


def seed_regional_pilot_crop_demo_if_empty(db: Session):
    if db.query(models.Household).filter(models.Household.name == _marker_household_name("고추")).first():
        return

    today = dt.date.today()
    random.seed(43)

    for crop_name in DEMO_PILOT_CROPS:
        crop = db.query(models.Crop).filter(models.Crop.name_kr == crop_name).first()
        if not crop:
            continue

        pest_pool = (
            db.query(models.TreatmentReference)
            .filter(models.TreatmentReference.crop_id == crop.id, models.TreatmentReference.is_active.is_(True))
            .all()
        )
        if not pest_pool:
            continue

        household = models.Household(
            name=_marker_household_name(crop_name),
            join_code=f"DEMOZ{crop_name[0]}",
        )
        db.add(household)
        db.flush()

        user = models.User(
            phone=f"0100000{DEMO_PILOT_CROPS.index(crop_name)}000",
            name=f"{crop_name} 지역통계 샘플 담당자",
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(models.HouseholdMember(household_id=household.id, user_id=user.id))

        for r in REGIONAL_DEMO_REGIONS:
            farm = models.Farm(
                household_id=household.id,
                crop_id=crop.id,
                farm_name=f"[샘플] {r['region']} {crop_name}시범농장",
                address=f"{r['address']} (샘플 데이터)",
                region=r["region"],
                latitude=r["latitude"] + random.uniform(-0.02, 0.02),
                longitude=r["longitude"] + random.uniform(-0.02, 0.02),
                area_pyeong=300,
                area_m2=991,
                facility_type="노지",
                cultivation_year=1,
            )
            db.add(farm)
            db.flush()

            for _ in range(random.randint(2, 9)):
                pest = random.choice(pest_pool)
                occ_date = today - dt.timedelta(days=random.randint(0, 120))
                eco, chemical = build_treatment_lists(pest)
                db.add(
                    models.Diagnosis(
                        farm_id=farm.id,
                        diagnosis_type=pest.type,
                        crop_name=crop_name,
                        occurrence_date=occ_date,
                        ai_disease_name=pest.name_kr,
                        ai_disease_name_en=pest.name_en,
                        ai_symptoms=pest.symptoms,
                        ai_confidence=round(random.uniform(0.65, 0.92), 2),
                        eco_treatments_json=json.dumps(eco, ensure_ascii=False),
                        chemical_treatments_json=json.dumps(chemical, ensure_ascii=False),
                        ai_source="demo",
                        status="분석완료",
                        farmer_confirmed_correct=random.choices([True, False, None], weights=[50, 15, 35])[0],
                    )
                )
        db.commit()
