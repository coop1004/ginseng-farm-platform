import datetime as dt
import json
import random
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.auth_service import hash_password
from app.services.reference_service import sync_pest_disease_materials

ECO_DB_PATH = Path(__file__).resolve().parent / "data" / "eco_treatment_db.json"

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


def _seasonal_weather(d: dt.date) -> dict:
    """월별로 그럴듯한 기상값을 생성한다 (weather_service의 데모 로직과 동일한 패턴)."""
    if d.month in (6, 7, 8):
        temp = round(random.uniform(24, 31), 1)
        humidity = round(random.uniform(75, 95), 1)
        rainfall = round(random.uniform(0, 25), 1)
    elif d.month in (3, 4, 5, 9, 10, 11):
        temp = round(random.uniform(10, 22), 1)
        humidity = round(random.uniform(45, 75), 1)
        rainfall = round(random.uniform(0, 10), 1)
    else:
        temp = round(random.uniform(-5, 5), 1)
        humidity = round(random.uniform(30, 55), 1)
        rainfall = 0.0
    wind = round(random.uniform(0.5, 4.0), 1)
    return {"temp_c": temp, "humidity_percent": humidity, "rainfall_mm": rainfall, "wind_ms": wind}


def _seed_weather_history(db: Session, farm: models.Farm, today: dt.date, days: int = 45):
    """진단 발생 여부와 무관하게 매일 쌓이는 기상 기록을 과거 N일치 미리 채워둔다
    (실제 운영에서는 /api/admin/weather/collect가 매일 이 역할을 대신한다)."""
    if farm.latitude is None or farm.longitude is None:
        return
    for days_ago in range(days):
        record_date = today - dt.timedelta(days=days_ago)
        weather = _seasonal_weather(record_date)
        db.add(
            models.WeatherRecord(
                farm_id=farm.id,
                record_date=record_date,
                temp_c=weather["temp_c"],
                humidity_percent=weather["humidity_percent"],
                rainfall_mm=weather["rainfall_mm"],
                wind_ms=weather["wind_ms"],
                source="demo",
            )
        )


def seed_default_organization_if_empty(db: Session):
    """지금 유일한 회원사("농자재회사A")를 organizations 테이블에 심는다. 다른 모든 시드
    함수보다 먼저 호출되어야 한다 - Household/Farm/Diagnosis/Notification/컨설턴트 계정·배정이
    전부 organization_id 컬럼의 기본값(models.DEFAULT_ORGANIZATION_ID=1)으로 이 행을 참조하므로,
    반드시 이 함수가 만드는 첫 번째(=id 1) organizations 행이어야 한다."""
    if db.query(models.Organization).count() > 0:
        return
    db.add(models.Organization(name="농자재회사A", org_type="농자재회사"))
    db.commit()


GINSENG_GROWTH_STAGES = ["1년근", "2년근", "3년근", "4년근", "5년근", "6년근"]

PILOT_CROPS = [
    dict(name_kr="인삼", name_en="Ginseng", icon_emoji="🌱", is_sample_data=False, sort_order=0),
    dict(name_kr="고추", name_en="Chili Pepper", icon_emoji="🌶️", is_sample_data=True, sort_order=1),
    dict(name_kr="배추", name_en="Napa Cabbage", icon_emoji="🥬", is_sample_data=True, sort_order=2),
]


def seed_crops_if_empty(db: Session):
    """작물 마스터가 하나도 없으면(최초 배포, 혹은 다작물 구조 도입 이전 운영 DB) 인삼/고추/
    배추를 등록한다. 인삼은 실서비스 작물(is_sample_data=False), 고추/배추는 구조 확장을
    보여주기 위한 파일럿(is_sample_data=True)로 표시된다. 인삼의 생육단계는 기존
    Farm.cultivation_year("1~6년근") 개념과 별개로, 신규 구조에서도 동일하게 6단계로 채워
    다른 작물과 같은 방식(growth_stage_id)으로도 조회할 수 있게 해둔다."""
    if db.query(models.Crop).count() > 0:
        return
    for c in PILOT_CROPS:
        crop = models.Crop(**c, is_active=True)
        db.add(crop)
        db.flush()
        if crop.name_kr == "인삼":
            for i, stage_name in enumerate(GINSENG_GROWTH_STAGES):
                db.add(models.GrowthStage(crop_id=crop.id, name_kr=stage_name, sort_order=i))
    db.commit()


def get_ginseng_crop_id(db: Session) -> int:
    crop = db.query(models.Crop).filter(models.Crop.name_kr == "인삼").first()
    if not crop:
        raise RuntimeError("인삼 Crop 시드가 아직 실행되지 않았습니다. seed_crops_if_empty를 먼저 호출하세요.")
    return crop.id


def backfill_crop_ids_if_missing(db: Session):
    """crop_id 컬럼이 새로 추가된 기존 운영 DB(농장/병해충참고자료)에서, 아직 crop_id가
    비어있는 행을 전부 인삼으로 채운다. seed_crops_if_empty 다음에 반드시 실행되어야
    하며, 이후로는 어떤 요청이 들어와도 crop_id가 비어있는 상태를 마주치지 않는다."""
    ginseng_id = get_ginseng_crop_id(db)

    farms_updated = (
        db.query(models.Farm)
        .filter(models.Farm.crop_id.is_(None))
        .update({models.Farm.crop_id: ginseng_id}, synchronize_session=False)
    )
    refs_updated = (
        db.query(models.TreatmentReference)
        .filter(models.TreatmentReference.crop_id.is_(None))
        .update({models.TreatmentReference.crop_id: ginseng_id}, synchronize_session=False)
    )
    if farms_updated or refs_updated:
        db.commit()


def backfill_pest_disease_materials_if_missing(db: Session):
    """agri_materials/pest_disease_materials 조인 테이블 도입 이전에 만들어진
    TreatmentReference 행(예: eco_treatment_db.json에서 1회 이관된 인삼 7종)은
    eco_treatments_json/chemical_treatments_json에는 자재 정보가 있지만 조인 테이블에는
    아무 연결이 없다. reference.py/gemini_service가 이제 조인 테이블만 신뢰하므로,
    이 상태를 그대로 두면 AI 진단 결과에서 방제 자재가 조용히 비어버린다(인삼 기존
    기능 회귀). 조인이 하나도 없는 행을 찾아 레거시 JSON에서 1회 채워 넣는다."""
    rows = db.query(models.TreatmentReference).all()
    for row in rows:
        if row.materials:
            continue
        eco = json.loads(row.eco_treatments_json) if row.eco_treatments_json else []
        chemical = json.loads(row.chemical_treatments_json) if row.chemical_treatments_json else []
        if not eco and not chemical:
            continue
        sync_pest_disease_materials(db, row, eco, chemical)
    db.commit()


def backfill_household_crops_if_missing(db: Session):
    """household_crops(농가가 등록한 작물 범위)가 하나도 없는 household마다 채운다.
    모든 데모/파일럿 작물 Farm이 이미 시딩된 뒤에 호출되어야 한다 — 각 household가
    실제로 보유한 Farm.crop_id들의 distinct 값을 등록하고(2/3단계에서 만든 고추/배추
    전용 샘플 household가 엉뚱하게 인삼까지 등록되는 걸 방지), 필지가 하나도 없는
    household만 인삼을 기본값으로 채운다(신규 가입 직후 농장을 아직 안 만든 인삼 농가는
    이 케이스에 해당하지 않는다 — register_new_household가 가입 시점에 이미 채워준다)."""
    ginseng_id = get_ginseng_crop_id(db)

    households = db.query(models.Household).all()
    for household in households:
        if db.query(models.HouseholdCrop).filter(models.HouseholdCrop.household_id == household.id).first():
            continue

        crop_ids = {
            row[0]
            for row in db.query(models.Farm.crop_id)
            .filter(models.Farm.household_id == household.id, models.Farm.crop_id.isnot(None))
            .distinct()
            .all()
        }
        if not crop_ids:
            crop_ids = {ginseng_id}

        for crop_id in crop_ids:
            db.add(models.HouseholdCrop(household_id=household.id, crop_id=crop_id))
    db.commit()


# region 자유 텍스트 중 "군/시"만 붙이면 바로 표준 시/군/구명이 되는 단순 케이스.
# "풍기"처럼 애초에 시/군 단위가 아닌 값(영주시 산하 읍 이름)은 여기 넣지 않고
# backfill_farm_region_if_needed가 address 문자열에서 실제 시/군을 다시 찾는다.
_REGION_SUFFIX_BACKFILL_MAP = {
    "금산": "금산군",
    "강화": "강화군",
    "진안": "진안군",
    "장수": "장수군",
    "음성": "음성군",
}


def backfill_farm_region_if_needed(db: Session):
    """seed_administrative_regions_if_empty 이후에 실행되어야 한다. farm.region이
    표준 시/군/구 목록에 없는 예전 자유 텍스트 값으로 남아있으면 정정한다 - 접미사만
    붙이면 되는 단순 케이스는 매핑표로, 그 외(예: "풍기")는 address 문자열에서 표준
    목록에 있는 시/군/구명을 다시 찾아 대체한다(가장 길게 일치하는 이름을 채택해
    짧은 이름끼리의 우연한 부분일치를 피한다)."""
    valid_sigungu = {row[0] for row in db.query(models.AdministrativeRegion.sigungu).all()}
    if not valid_sigungu:
        return

    farms = db.query(models.Farm).filter(models.Farm.region.isnot(None)).all()
    updated = 0
    for farm in farms:
        region = farm.region
        if not region or region in valid_sigungu:
            continue

        if region in _REGION_SUFFIX_BACKFILL_MAP:
            farm.region = _REGION_SUFFIX_BACKFILL_MAP[region]
            updated += 1
            continue

        matches = [sigungu for sigungu in valid_sigungu if sigungu in (farm.address or "")]
        if matches:
            farm.region = max(matches, key=len)
            updated += 1

    if updated:
        db.commit()


def seed_admin_if_empty(db: Session):
    """운영 DB에 이미 농가 데이터가 있어도(= seed_if_empty가 건너뛰어도) 관리자 계정이
    하나도 없으면 부트스트랩 계정을 만든다. 최초 배포 시 1회만 실행됨."""
    if db.query(models.AdminUser).count() > 0:
        return
    db.add(
        models.AdminUser(
            username=settings.admin_bootstrap_username,
            name="관리자",
            password_hash=hash_password(settings.admin_bootstrap_password),
            is_protected=True,
        )
    )
    db.commit()


def seed_demo_consultant_if_empty(db: Session):
    """데모/테스트 편의를 위해 컨설턴트 계정이 하나도 없으면 1개 만들고, 이미 시딩된
    데모 농가 중 처음 두 곳(김인삼 농가, 박풍기 농가)을 담당 농가로 배정해둔다.
    seed_if_empty 이후에 호출되어야 한다(그 함수가 만드는 household를 배정 대상으로 씀)."""
    if db.query(models.ConsultantUser).count() > 0:
        return
    consultant = models.ConsultantUser(
        username="consultant1",
        name="정병해 컨설턴트",
        password_hash=hash_password(DEMO_PASSWORD),
    )
    db.add(consultant)
    db.flush()

    demo_households = (
        db.query(models.Household)
        .filter(models.Household.join_code.in_(["DEMO01", "DEMO02"]))
        .all()
    )
    for household in demo_households:
        db.add(models.ConsultantHousehold(consultant_id=consultant.id, household_id=household.id))
    db.commit()


def seed_community_channel_posts_if_empty(db: Session):
    """커뮤니티 화면이 콘텐츠 공백으로 죽은 공간처럼 보이지 않도록, 데모 컨설턴트가
    담당 농가에 올린 채널 공지/팁 글을 몇 개 시드해둔다. seed_demo_consultant_if_empty
    이후에 호출되어야 한다(그 함수가 만드는 컨설턴트 계정을 글쓴이로 씀)."""
    if db.query(models.CommunityPost).count() > 0:
        return
    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.username == "consultant1").first()
    if not consultant:
        return
    ginseng = db.query(models.Crop).filter(models.Crop.name_kr == "인삼").first()

    posts = [
        {
            "title": "장마철 뿌리썩음병 예방 안내",
            "body": "최근 강우량이 많은 지역에서 뿌리썩음병 발생이 늘고 있습니다. "
            "배수로 점검을 미리 해주시고, 해가림 시설 하부 습도 관리에 신경써주세요.",
            "visibility": "consultant_scope",
        },
        {
            "title": "이번 주 방제 팁 - 친환경 자재 우선 추천",
            "body": "확산 초기에는 화학 자재보다 친환경 자재로 먼저 대응해보시고, "
            "1주일 후에도 증상이 진행되면 화학 방제로 전환하시는 걸 권장드립니다.",
            "visibility": "consultant_scope",
        },
    ]
    for p in posts:
        db.add(
            models.CommunityPost(
                title=p["title"],
                body=p["body"],
                kind="channel",
                crop_id=ginseng.id if ginseng else None,
                visibility=p["visibility"],
                author_type="consultant",
                author_consultant_id=consultant.id,
                author_name=consultant.name,
            )
        )
    db.commit()


def ensure_protected_admin(db: Session):
    """보호된(삭제 불가) 관리자 계정이 하나도 없으면, 가장 먼저 만들어진 계정을
    보호 대상으로 지정한다. 매 서버 시작 시 실행되어, 다른 관리자에 의해 보호 계정이
    삭제된 과거 상태의 운영 DB도 다음 배포에서 자동으로 복구된다."""
    if db.query(models.AdminUser).filter(models.AdminUser.is_protected.is_(True)).count() > 0:
        return
    oldest = db.query(models.AdminUser).order_by(models.AdminUser.created_at, models.AdminUser.id).first()
    if oldest:
        oldest.is_protected = True
        db.commit()


def seed_if_empty(db: Session):
    if db.query(models.Household).count() > 0:
        return

    today = dt.date.today()
    random.seed(42)
    ginseng_id = get_ginseng_crop_id(db)

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
            crop_id=ginseng_id,
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
                extra_farm = models.Farm(household_id=household.id, crop_id=ginseng_id, **extra)
                db.add(extra_farm)
                db.flush()
                all_farms.append(extra_farm)

    db.commit()

    for farm in all_farms:
        _seed_farm_records(db, farm, today)
        _seed_weather_history(db, farm, today)
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


def seed_treatment_references_if_empty(db: Session):
    """병해충 참고자료가 DB에 하나도 없으면(최초 배포, 혹은 이 기능 도입 이전 운영 DB),
    기존 eco_treatment_db.json에 있던 7종을 1회 옮겨 담는다. 이후로는 관리자
    대시보드 CMS에서 DB를 직접 관리하고, 이 JSON 파일은 더 이상 참조되지 않는다."""
    if db.query(models.TreatmentReference).count() > 0:
        return
    if not ECO_DB_PATH.exists():
        return
    ginseng_id = get_ginseng_crop_id(db)
    with open(ECO_DB_PATH, "r", encoding="utf-8") as f:
        diseases = json.load(f)["diseases"]

    for d in diseases:
        cond = d.get("favorable_conditions", {})
        temp_range = cond.get("temp_range_c") or [None, None]
        db.add(
            models.TreatmentReference(
                crop_id=ginseng_id,
                crop_name=d.get("crop", "인삼"),
                type=d["type"],
                name_kr=d["name_kr"],
                name_en=d.get("name_en"),
                symptoms=d.get("symptoms"),
                cause=d.get("cause"),
                favorable_temp_min=temp_range[0],
                favorable_temp_max=temp_range[1],
                favorable_humidity_min=cond.get("humidity_min_percent"),
                favorable_rainfall_note=cond.get("rainfall"),
                eco_treatments_json=json.dumps(d.get("eco_treatments", []), ensure_ascii=False),
                chemical_treatments_json=json.dumps(d.get("chemical_treatments", []), ensure_ascii=False),
                is_active=True,
                updated_by="초기 마이그레이션",
            )
        )
    db.commit()
