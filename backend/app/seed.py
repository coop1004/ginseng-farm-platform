import datetime as dt
import json
import random

from sqlalchemy.orm import Session

from app import models
from app.services.auth_service import hash_password

DEMO_PASSWORD = "farm1234"  # 데모 계정 공통 비밀번호

HOUSEHOLDS = [
    dict(
        owner_name="김인삼",
        phone="01011112222",
        household_name="김인삼 농가",
        join_code="DEMO01",
        farm_name="금산 본가농원",
        address="충청남도 금산군 금산읍 인삼로 12",
        region="금산",
        latitude=36.1088,
        longitude=127.4880,
        area_pyeong=1500,
        area_m2=4958,
        facility_type="해가림",
        cultivation_year=4,
        phone_contact="010-1111-2222",
    ),
    dict(
        owner_name="박풍기",
        phone="01022223333",
        household_name="박풍기 농가",
        join_code="DEMO02",
        farm_name="풍기 명품인삼농장",
        address="경상북도 영주시 풍기읍 인삼시장길 7",
        region="풍기",
        latitude=36.8592,
        longitude=128.5219,
        area_pyeong=2200,
        area_m2=7273,
        facility_type="해가림",
        cultivation_year=5,
        phone_contact="010-2222-3333",
    ),
    dict(
        owner_name="이강화",
        phone="01033334444",
        household_name="이강화 농가",
        join_code="DEMO03",
        farm_name="강화 도라지골 삼포",
        address="인천광역시 강화군 불은면 삼포로 45",
        region="강화",
        latitude=37.6975,
        longitude=126.4467,
        area_pyeong=900,
        area_m2=2975,
        facility_type="노지",
        cultivation_year=2,
        phone_contact="010-3333-4444",
    ),
    dict(
        owner_name="최진안",
        phone="01044445555",
        household_name="최진안 농가",
        join_code="DEMO04",
        farm_name="진안 고원 스마트삼",
        address="전라북도 진안군 진안읍 고원로 88",
        region="진안",
        latitude=35.7917,
        longitude=127.4247,
        area_pyeong=1800,
        area_m2=5950,
        facility_type="스마트팜",
        cultivation_year=3,
        phone_contact="010-4444-5555",
    ),
    dict(
        owner_name="정장수",
        phone="01055556666",
        household_name="정장수 농가",
        join_code="DEMO05",
        farm_name="장수 뜬봉샘 인삼밭",
        address="전라북도 장수군 장수읍 뜬봉샘로 23",
        region="장수",
        latitude=35.6474,
        longitude=127.5209,
        area_pyeong=1100,
        area_m2=3636,
        facility_type="해가림",
        cultivation_year=6,
        phone_contact="010-5555-6666",
    ),
    dict(
        owner_name="한음성",
        phone="01066667777",
        household_name="한음성 농가",
        join_code="DEMO06",
        farm_name="음성 청결인삼영농조합",
        address="충청북도 음성군 음성읍 인삼길 5",
        region="음성",
        latitude=36.9397,
        longitude=127.6900,
        area_pyeong=1300,
        area_m2=4298,
        facility_type="노지",
        cultivation_year=1,
        phone_contact="010-6666-7777",
    ),
]

# 김인삼 농가는 필지를 2개 더 운영하는 시나리오(농가 1곳 - 여러 필지)를 데모로 보여준다.
EXTRA_FARMS_FOR_FIRST_HOUSEHOLD = [
    dict(
        farm_name="금산 2호 필지",
        address="충청남도 금산군 제원면 인삼로 45",
        region="금산",
        latitude=36.1245,
        longitude=127.5012,
        area_pyeong=800,
        area_m2=2645,
        facility_type="노지",
        cultivation_year=2,
        phone="010-1111-2222",
    ),
    dict(
        farm_name="금산 3호 필지(스마트팜)",
        address="충청남도 금산군 남일면 인삼로 78",
        region="금산",
        latitude=36.0891,
        longitude=127.4623,
        area_pyeong=1200,
        area_m2=3967,
        facility_type="스마트팜",
        cultivation_year=1,
        phone="010-1111-2222",
    ),
]

WORK_CONTENTS = [
    "해가림 시설 점검 및 차광막 보수 작업 실시",
    "인삼밭 잡초 제거 및 배수로 정비",
    "친환경 미생물 자재 예방 관주 처리",
    "신초 유인 작업 및 지주대 보강",
    "가을 수확을 위한 두둑 상태 점검",
    "관수 시설 점검 및 스프링클러 청소",
    "퇴비 및 유기질 비료 시비 작업",
    "병해충 예찰을 위한 포장 순회 점검",
    "태풍 대비 해가림 시설 결속 보강",
    "수확 후 포장 정리 및 내년 작기 준비",
]

DISEASE_POOL = [
    ("병해", "점무늬병(반점병)", "Alternaria Leaf Spot"),
    ("병해", "탄저병", "Anthracnose"),
    ("병해", "뿌리썩음병(근부병)", "Root Rot"),
    ("해충", "굼벵이(풍뎅이류 유충)", "White Grub"),
    ("해충", "진딧물", "Aphid"),
    ("생리장애", "일소(햇빛데임) 피해", "Sunscald"),
    ("생리장애", "칼슘결핍(생리장애)", "Calcium Deficiency"),
]


def _seed_farm_records(db: Session, farm: models.Farm, today: dt.date):
    num_logs = random.randint(8, 14)
    for _ in range(num_logs):
        days_ago = random.randint(0, 180)
        work_date = today - dt.timedelta(days=days_ago)
        db.add(
            models.WorkLog(
                farm_id=farm.id,
                work_date=work_date,
                work_area_m2=farm.area_m2,
                content=random.choice(WORK_CONTENTS),
            )
        )

    num_diag = random.randint(3, 7)
    for _ in range(num_diag):
        days_ago = random.randint(0, 150)
        occ_date = today - dt.timedelta(days=days_ago)
        dtype, name_kr, name_en = random.choice(DISEASE_POOL)

        month = occ_date.month
        if month in (6, 7, 8):
            temp = round(random.uniform(24, 31), 1)
            humidity = round(random.uniform(75, 95), 1)
            rainfall = round(random.uniform(0, 25), 1)
        else:
            temp = round(random.uniform(10, 22), 1)
            humidity = round(random.uniform(45, 75), 1)
            rainfall = round(random.uniform(0, 10), 1)
        wind = round(random.uniform(0.5, 4.0), 1)

        eco_treatments = [
            {
                "product_name": "그린가드 친환경 인삼 전용 미생물제제",
                "active_ingredient": "바실러스 서브틸리스 1억 CFU/g",
                "usage": "물 1000L당 500g 희석, 7일 간격 2~3회 엽면살포",
                "note": "예방 위주 사용 시 효과 극대화",
            }
        ]
        chemical_treatments = [
            {
                "product_name": "만코지 수화제",
                "active_ingredient": "만코지 75%",
                "usage": "1000배 희석 살포, 10일 간격",
                "note": "보조적 사용 권장",
            }
        ]

        confirmed = random.choices([True, False, None], weights=[55, 15, 30])[0]

        db.add(
            models.Diagnosis(
                farm_id=farm.id,
                diagnosis_type=dtype,
                crop_name="인삼",
                occurrence_date=occ_date,
                photo_path=None,
                gps_lat=farm.latitude,
                gps_lng=farm.longitude,
                photo_taken_at=dt.datetime.combine(occ_date, dt.time(hour=random.randint(7, 17))),
                weather_temp_c=temp,
                weather_humidity_percent=humidity,
                weather_rainfall_mm=rainfall,
                weather_wind_ms=wind,
                weather_source="demo",
                ai_disease_name=name_kr,
                ai_disease_name_en=name_en,
                ai_symptoms=f"{name_kr} 전형적 증상이 관찰되며, 당시 기온 {temp}℃·습도 {humidity}% 조건에서 발생 가능성이 높습니다.",
                ai_confidence=round(random.uniform(0.70, 0.96), 2),
                eco_treatments_json=json.dumps(eco_treatments, ensure_ascii=False),
                chemical_treatments_json=json.dumps(chemical_treatments, ensure_ascii=False),
                ai_source="demo",
                status="분석완료",
                farmer_confirmed_correct=confirmed,
            )
        )


def seed_if_empty(db: Session):
    if db.query(models.Household).count() > 0:
        return

    today = dt.date.today()
    random.seed(42)

    all_farms = []

    for h in HOUSEHOLDS:
        household = models.Household(name=h["household_name"], join_code=h["join_code"])
        db.add(household)
        db.flush()

        user = models.User(
            phone=h["phone"],
            name=h["owner_name"],
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.flush()

        db.add(models.HouseholdMember(household_id=household.id, user_id=user.id))

        farm = models.Farm(
            household_id=household.id,
            farm_name=h["farm_name"],
            address=h["address"],
            region=h["region"],
            latitude=h["latitude"],
            longitude=h["longitude"],
            area_pyeong=h["area_pyeong"],
            area_m2=h["area_m2"],
            facility_type=h["facility_type"],
            cultivation_year=h["cultivation_year"],
            phone=h["phone_contact"],
        )
        db.add(farm)
        db.flush()
        all_farms.append(farm)

        # 첫 번째 농가는 필지 3개(1농가-다필지) 시나리오를 보여준다.
        if h is HOUSEHOLDS[0]:
            for extra in EXTRA_FARMS_FOR_FIRST_HOUSEHOLD:
                extra_farm = models.Farm(household_id=household.id, **extra)
                db.add(extra_farm)
                db.flush()
                all_farms.append(extra_farm)

    db.commit()

    for farm in all_farms:
        _seed_farm_records(db, farm, today)
    db.commit()

    # 관리자 알림 시뮬레이션 샘플
    sample_farm = all_farms[0]
    db.add(
        models.Notification(
            farm_id=sample_farm.id,
            title="점무늬병 예방 처방 안내",
            message="최근 고온다습 조건이 지속되어 점무늬병 발생 위험이 높습니다. 예방 차원에서 친환경 미생물제제 살포를 권장드립니다.",
            recommended_product="그린가드 친환경 인삼 전용 미생물제제",
            sent_by="관리자",
            status="발송됨",
        )
    )
    db.commit()
