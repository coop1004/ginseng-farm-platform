import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    """회원사(농자재회사/컨설턴트그룹/기술센터/생산자단체 등). 지금은 "농자재회사A" 하나뿐이지만,
    핵심 테이블(농가/농장/진단/처방/컨설턴트 계정·배정)에 organization_id를 미리 붙여둬서
    나중에 회원사가 늘어날 때 데이터 구조를 바꾸지 않고 확장할 수 있도록 준비해둔다. 회사별
    전환 UI, 권한 분리 로직, 회사 관리자 화면은 아직 만들지 않았다 - 실제 두 번째 회원사가
    생길 때 별도로 구현한다."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    # 자유 텍스트: 농자재회사 / 컨설턴트그룹 / 기술센터 / 생산자단체 등. 지금은 값만 채워두고
    # 유형별로 다르게 동작하는 로직은 아직 없다.
    org_type = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


# 지금 유일한 회원사("농자재회사A")의 id. 아래 핵심 테이블들의 organization_id 기본값으로
# 쓰인다 - seed.seed_default_organization_if_empty가 다른 모든 시드보다 먼저 실행되어 이
# id로 그 행을 만들어둔다. 두 번째 회원사가 생기기 전까지는 이 상수 하나만 바꾸면 새로
# 생성되는 데이터의 기본 소속을 전환할 수 있다.
DEFAULT_ORGANIZATION_ID = 1


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    username = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # 최초(부트스트랩) 관리자 계정 표시. 이 계정은 다른 관리자가 삭제할 수 없다
    # (신규로 추가된 관리자가 실수/악의로 나머지 계정을 전부 지워 아무도 못 들어오는 상황 방지).
    is_protected = Column(Boolean, default=False, nullable=False)
    # "platform_super"(찬파트너스 내부 운영 인력 - 조직을 넘나들며 전체 관리, organization_id는
    # 자기 소속을 뜻하지 않음) / "org_scoped"(특정 조직 하나로 접근이 제한되는 계정 - 지금은
    # 실제로 발급되지 않고, 향후 기관/회사 자체 관리자 계정을 위한 자리만 마련해둔다).
    role = Column(String(20), nullable=False, default="platform_super")
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class ConsultantUser(Base):
    """병해충 진단 컨설턴트 계정. AdminUser(회사 관리자, 전체 농가 무제한 접근)와는
    완전히 별개의 인증 체계 — 관리자가 배정한(ConsultantHousehold) 담당 농가로만
    접근 범위가 제한된다."""

    __tablename__ = "consultant_users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    username = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(30), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    households = relationship("Household", secondary="consultant_households", viewonly=True)


class ConsultantHousehold(Base):
    """컨설턴트의 담당 농가 배정. HouseholdCrop과 동일한 다대다 매핑 패턴 —
    관리자가 이 테이블을 직접 추가/삭제해서 배정/해제한다."""

    __tablename__ = "consultant_households"
    __table_args__ = (UniqueConstraint("consultant_id", "household_id", name="uq_consultant_household"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    consultant_id = Column(Integer, ForeignKey("consultant_users.id"), nullable=False)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    assigned_at = Column(DateTime, default=dt.datetime.utcnow)

    consultant = relationship("ConsultantUser")
    household = relationship("Household")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    memberships = relationship("HouseholdMember", back_populates="user", cascade="all, delete-orphan")


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    name = Column(String(100), nullable=False)  # 농가명 (대표자/농가 이름)
    join_code = Column(String(10), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    members = relationship("HouseholdMember", back_populates="household", cascade="all, delete-orphan")
    farms = relationship("Farm", back_populates="household", cascade="all, delete-orphan")
    # HouseholdOut.model_validate(household)가 crops를 바로 읽을 수 있도록 하는 읽기 전용 편의
    # 릴레이션 — 실제 등록/해제는 HouseholdCrop 행을 직접 추가/삭제해서 한다(unique 제약,
    # created_at 등을 다루려면 이쪽이 더 명확함).
    crops = relationship("Crop", secondary="household_crops", viewonly=True, order_by="Crop.sort_order")
    # 관리자 대시보드 농가 상세 화면에서 "담당 컨설턴트" 표시용 읽기 전용 편의 릴레이션.
    consultants = relationship("ConsultantUser", secondary="consultant_households", viewonly=True)


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_household_user"),)

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household", back_populates="members")
    user = relationship("User", back_populates="memberships")


class HouseholdCrop(Base):
    """농가(household)가 "등록한" 작물 목록 — Farm.crop_id(그 필지가 어떤 작물인지)와는
    다른 개념으로, 농가 계정이 앱에서 노출받을 작물 범위를 나타낸다. 인삼만 등록된 농가는
    모바일 화면에서 다른 작물을 아예 볼 수 없고(작물 선택/전환 UI도 안 보임), API 레벨에서도
    등록하지 않은 crop_id는 조회/생성이 막힌다."""

    __tablename__ = "household_crops"
    __table_args__ = (UniqueConstraint("household_id", "crop_id", name="uq_household_crop"),)

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household")
    crop = relationship("Crop")


class Crop(Base):
    """지원 작물 마스터. 인삼 외 작물로 확장하기 위한 기준 축 — Farm/TreatmentReference/
    GrowthStage가 전부 이 테이블의 id를 기준으로 연결된다."""

    __tablename__ = "crops"

    id = Column(Integer, primary_key=True, index=True)
    name_kr = Column(String(50), unique=True, nullable=False)
    name_en = Column(String(50), nullable=True)
    icon_emoji = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # 실제 학습된 진단 데이터/약제 정보 없이 시연용으로 등록된 파일럿 작물인지 여부.
    # True면 모바일 진단결과 화면에 "샘플 데이터"/"베타 모델" 안내를 띄우는 기준이 된다.
    is_sample_data = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    growth_stages = relationship("GrowthStage", back_populates="crop", cascade="all, delete-orphan")


class GrowthStage(Base):
    """작물별 생육단계. 인삼은 seed 단계에서 '1년근'~'6년근' 6개로 채워지고(기존
    Farm.cultivation_year 개념과 별개로 존재 — cultivation_year는 그대로 둠), 다른
    작물은 정식기/생육기/수확기 등 실제 생육단계로 채워진다."""

    __tablename__ = "growth_stages"

    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=False)
    name_kr = Column(String(50), nullable=False)
    sort_order = Column(Integer, default=0)
    description = Column(Text, nullable=True)

    crop = relationship("Crop", back_populates="growth_stages")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=True)  # seed 직후 항상 채워짐(앱 레벨 필수 취급)
    growth_stage_id = Column(Integer, ForeignKey("growth_stages.id"), nullable=True)  # 인삼 농장은 비워둠
    farm_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    region = Column(String(50), index=True)  # 시/군/구 단위 (지도/통계 그룹핑용)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_pyeong = Column(Float, default=0)
    area_m2 = Column(Float, default=0)
    facility_type = Column(String(20), default="노지")  # 노지 / 해가림 / 스마트팜
    cultivation_year = Column(Integer, default=1)  # 1~6년근 (인삼 전용 개념, 손대지 않음)
    phone = Column(String(30), nullable=True)
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household", back_populates="farms")
    crop = relationship("Crop")
    growth_stage = relationship("GrowthStage")
    work_logs = relationship("WorkLog", back_populates="farm", cascade="all, delete-orphan")
    diagnoses = relationship("Diagnosis", back_populates="farm", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="farm", cascade="all, delete-orphan")


class WorkLog(Base):
    __tablename__ = "work_logs"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    work_date = Column(Date, default=dt.date.today)
    photo_path = Column(String(255), nullable=True)
    work_area_m2 = Column(Float, default=0)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    farm = relationship("Farm", back_populates="work_logs")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)

    diagnosis_type = Column(String(20), nullable=False)  # 병해 / 해충 / 생리장애
    crop_name = Column(String(50), default="인삼")
    occurrence_date = Column(Date, default=dt.date.today)
    photo_path = Column(String(255), nullable=True)

    # EXIF로부터 추출한 정보. 사진에 GPS/촬영시각이 없으면(카카오톡 전달, 편집본, 위치권한
    # 꺼짐 등) gps_estimated/photo_taken_at_estimated로 대체값이 쓰였음을 표시한다 -
    # 값 자체(gps_lat 등)만 보고는 "실제 촬영 위치"인지 "농장 등록 주소로 대체"한 건지
    # 구분할 수 없기 때문에 별도 플래그로 남긴다.
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    gps_estimated = Column(Boolean, default=False, nullable=False)  # True면 농장 등록 주소로 대체된 좌표
    photo_taken_at = Column(DateTime, nullable=True)
    photo_taken_at_estimated = Column(Boolean, default=False, nullable=False)  # True면 업로드 시각으로 대체됨

    # OpenWeather 연동 결과. gps_lat/lng을 전혀 알 수 없을 때(사진 EXIF도 없고 농장 주소도
    # 미등록)는 위치 기반 날씨를 추정할 근거가 없으므로 weather_source="unavailable"로 남기고
    # weather_* 필드는 전부 비워둔다 - 이 경우 데모 시즌 날씨를 채워넣지 않는다(사실과 무관한
    # 값이 마치 실제 날씨인 것처럼 보이는 걸 방지).
    weather_temp_c = Column(Float, nullable=True)
    weather_humidity_percent = Column(Float, nullable=True)
    weather_rainfall_mm = Column(Float, nullable=True)
    weather_wind_ms = Column(Float, nullable=True)
    weather_source = Column(String(20), nullable=True)  # openweather_current / openweather_timemachine / demo / unavailable

    # Gemini 진단 결과
    ai_disease_name = Column(String(100), nullable=True)
    ai_disease_name_en = Column(String(100), nullable=True)
    ai_symptoms = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    eco_treatments_json = Column(Text, nullable=True)  # JSON string
    chemical_treatments_json = Column(Text, nullable=True)  # JSON string
    ai_raw_response = Column(Text, nullable=True)
    ai_source = Column(String(20), nullable=True)  # gemini / demo

    status = Column(String(20), default="분석완료")  # 분석중 / 분석완료 / 실패
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    # 농가 사후 피드백: AI 예측이 실제와 맞았는지 (통계 - AI 예측 대비 실제 발생 비교용)
    farmer_confirmed_correct = Column(Boolean, nullable=True)

    # 사람(농가 본인 또는 전문가)이 AI 판단과 다르게 확인/정정한 최종 진단명.
    # AI가 진단 실패했거나(status=분석실패), 확신도가 낮거나, 단순히 AI 결과가 틀렸을 때
    # 현장을 실제로 본 사람의 판단을 최종 처방/통계의 기준으로 삼기 위함.
    # 존재하면 ai_disease_name보다 항상 우선한다.
    final_disease_name = Column(String(100), nullable=True)
    final_diagnosis_source = Column(String(20), nullable=True)  # farmer / expert / consultant
    final_diagnosis_note = Column(Text, nullable=True)
    final_diagnosis_by = Column(String(50), nullable=True)  # 입력자 이름
    final_diagnosis_at = Column(DateTime, nullable=True)

    # 이 진단을 최초 등록한 주체. 기존 행은 전부 농가 본인이 등록한 것이므로 기본값
    # "household"로 자연스럽게 해석된다(백필 불필요) - 컨설턴트가 현장 방문 중 등록한
    # 경우만 "consultant"+created_by_consultant_id가 채워진다.
    created_by_type = Column(String(20), nullable=False, default="household")  # household / consultant
    created_by_consultant_id = Column(Integer, ForeignKey("consultant_users.id"), nullable=True)

    farm = relationship("Farm", back_populates="diagnoses")
    photos = relationship("DiagnosisPhoto", back_populates="diagnosis", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="diagnosis")
    created_by_consultant = relationship("ConsultantUser")
    comments = relationship(
        "DiagnosisComment", back_populates="diagnosis", cascade="all, delete-orphan",
        order_by="DiagnosisComment.created_at",
    )


class DiagnosisPhoto(Base):
    """진단 1건에 여러 장의 피해 사진을 첨부할 수 있도록 하는 자식 테이블.
    Diagnosis.photo_path는 기존 화면(관리자 갤러리 썸네일, PDF 등) 호환을 위해
    첫 번째 사진 경로를 그대로 유지한다."""

    __tablename__ = "diagnosis_photos"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=False)
    photo_path = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    diagnosis = relationship("Diagnosis", back_populates="photos")


class DiagnosisComment(Base):
    """진단 1건에 여러 명(농가 본인, 컨설턴트)이 남기는 코멘트 스레드.
    final_diagnosis_note(단일 슬롯, 덮어쓰기)와 달리 여러 개가 쌓이며,
    작성자 종류와 상관없이 같은 진단을 보는 모두에게 노출된다."""

    __tablename__ = "diagnosis_comments"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=False)

    author_type = Column(String(20), nullable=False)  # household / consultant
    author_name = Column(String(50), nullable=False)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    author_consultant_id = Column(Integer, ForeignKey("consultant_users.id"), nullable=True)

    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    diagnosis = relationship("Diagnosis", back_populates="comments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=True)

    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    recommended_product = Column(String(150), nullable=True)
    sent_by = Column(String(50), default="관리자")
    status = Column(String(20), default="발송됨")  # 발송됨 / 확인됨
    # 여러 농가에 한 번에 보낸 공지(브로드캐스트)일 때, 같은 발송 건임을 묶어주는 식별자.
    # 개별 농가에 보낸 알림은 null.
    broadcast_group = Column(String(40), nullable=True, index=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    farm = relationship("Farm", back_populates="notifications")
    diagnosis = relationship("Diagnosis", back_populates="notifications")


class WeatherRecord(Base):
    """농장 위치의 일별 기상 스냅샷. 진단이 없는 날에도 매일 쌓여서
    추후 병해충 발생과 기상 패턴의 상관관계 분석(예측 모델 등)에 사용된다."""

    __tablename__ = "weather_records"
    __table_args__ = (UniqueConstraint("farm_id", "record_date", name="uq_weather_farm_date"),)

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    record_date = Column(Date, nullable=False, index=True)

    temp_c = Column(Float, nullable=True)
    humidity_percent = Column(Float, nullable=True)
    rainfall_mm = Column(Float, nullable=True)
    wind_ms = Column(Float, nullable=True)
    source = Column(String(20), nullable=True)  # openweather_current / demo

    created_at = Column(DateTime, default=dt.datetime.utcnow)

    farm = relationship("Farm")


class TreatmentReference(Base):
    """회사가 보유한 병해충/생리장애 참고자료(=pest_disease) + 방제 자재 정보. AI 진단
    프롬프트의 근거 자료로 쓰이고, 관리자 대시보드 CMS에서 직접 추가/수정한다.

    eco_treatments_json/chemical_treatments_json은 하위호환용 원본 필드로 계속 저장되지만,
    실제 조회는 PestDiseaseMaterial 조인 테이블을 우선한다(get-or-create로 AgriMaterial과
    연결됨) — CMS 화면(관리자 대시보드)의 입력 방식은 그대로 두고 내부만 정규화했다."""

    __tablename__ = "treatment_references"

    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=True)  # seed 직후 항상 채워짐(앱 레벨 필수 취급)
    crop_name = Column(String(50), nullable=False, default="인삼")  # 이력 표시 스냅샷, 필터링에는 crop_id만 사용
    type = Column(String(20), nullable=False)  # 병해 / 해충 / 생리장애
    name_kr = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    symptoms = Column(Text, nullable=True)
    cause = Column(Text, nullable=True)

    # 발생 유리 조건 (데모 진단의 후보 스코어링, 참고용 표시에 사용)
    favorable_temp_min = Column(Float, nullable=True)
    favorable_temp_max = Column(Float, nullable=True)
    favorable_humidity_min = Column(Float, nullable=True)
    favorable_rainfall_note = Column(String(50), nullable=True)  # 예: "많음" / "적음" (자유 텍스트)

    eco_treatments_json = Column(Text, nullable=True)  # JSON: [{product_name, active_ingredient, usage, note}]
    chemical_treatments_json = Column(Text, nullable=True)

    photo_path = Column(String(255), nullable=True)  # 병해충 참고 사진(플레이스홀더 포함)
    # 실제 학습 데이터 없이 등록된 파일럿 작물용 샘플 항목 표시(행 단위 보조 플래그).
    # 실제 배지/문구 판단 기준은 crops.is_sample_data 쪽을 우선 사용한다.
    is_sample_data = Column(Boolean, default=False, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    updated_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    crop = relationship("Crop")
    materials = relationship("PestDiseaseMaterial", back_populates="pest_disease", cascade="all, delete-orphan")


class AgriMaterial(Base):
    """방제 자재(농자재) 카탈로그. 병해충 참고자료(TreatmentReference)에서 재사용되는
    친환경/화학 자재 마스터 — 같은 자재를 여러 병해충에 중복 입력하지 않도록 분리.

    organization_id: 병해충정보(TreatmentReference)와 달리 자재 카탈로그는 회사별로
    갖는 게 자연스러워 organization_id를 붙였다. 지금은 조회/저장 시 이 값으로
    필터링하는 로직은 없다(자리만 마련 - 다른 핵심 테이블과 동일한 수준)."""

    __tablename__ = "agri_materials"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    name = Column(String(150), nullable=False, unique=True)
    category = Column(String(20), nullable=False)  # 친환경 / 화학
    active_ingredient = Column(String(255), nullable=True)
    default_usage = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class PestDiseaseMaterial(Base):
    """TreatmentReference(병해충) ↔ AgriMaterial(농자재) 다대다 연결. usage/note를
    이 병해충에 한해 다르게 쓰고 싶을 때만 override 필드를 채우고, 없으면 자재의
    기본값(default_usage/note)을 그대로 쓴다. 친환경/화학 구분은 자재 자체의
    category로만 판단한다(별도 role 컬럼을 두지 않아 데이터 불일치 가능성을 없앰).

    organization_id: "어떤 회사가 어떤 병해충에 어떤 자재를 추천하는지"의 매핑 자체가
    회사별로 달라질 수 있어 붙였다 - 공용인 병해충정보(pest_disease)와 회사별 자재
    카탈로그를 잇는 이 연결 테이블이 다대다 관계의 실질적인 "회사별 분리 지점"이다."""

    __tablename__ = "pest_disease_materials"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, default=DEFAULT_ORGANIZATION_ID)
    pest_disease_id = Column(Integer, ForeignKey("treatment_references.id"), nullable=False)
    agri_material_id = Column(Integer, ForeignKey("agri_materials.id"), nullable=False)
    usage_override = Column(Text, nullable=True)
    note_override = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    pest_disease = relationship("TreatmentReference", back_populates="materials")
    agri_material = relationship("AgriMaterial")


class CommunityPost(Base):
    """농가-농가, 농가-컨설턴트 커뮤니티 게시글. kind로 글의 성격을 구분한다:
    channel(컨설턴트가 담당 농가에 올리는 공지/팁) / diagnosis_share(농가가 옵트인으로
    공개한 진단 기록) / free(추후 확장용 자유게시판, 현재 미사용). 원본 Diagnosis 행에는
    공개 플래그를 두지 않고, 공유할 때만 이 테이블에 새 글이 생기는 구조로 옵트인을
    구조적으로 강제한다 - 진단이 실수로 공개되는 사고를 원천 차단하기 위함."""

    __tablename__ = "community_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    body = Column(Text, nullable=True)
    photo_paths_json = Column(Text, nullable=True)  # JSON string, DiagnosisPhoto와 달리 자식 테이블 없이 스냅샷으로 보관

    kind = Column(String(20), nullable=False)  # channel / diagnosis_share / free
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=True)  # kind=diagnosis_share일 때만

    # public: 전체 로그인 사용자 / consultant_scope: 글쓴이와 같은 컨설턴트가 담당하는 농가끼리만
    visibility = Column(String(20), nullable=False, default="public")

    author_type = Column(String(20), nullable=False)  # household / consultant / admin
    author_household_id = Column(Integer, ForeignKey("households.id"), nullable=True)
    author_consultant_id = Column(Integer, ForeignKey("consultant_users.id"), nullable=True)
    author_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    author_name = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False, default="visible")  # visible / hidden
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    crop = relationship("Crop")
    diagnosis = relationship("Diagnosis")
    household = relationship("Household")
    consultant = relationship("ConsultantUser")
    comments = relationship(
        "CommunityComment", back_populates="post", cascade="all, delete-orphan",
        order_by="CommunityComment.created_at",
    )


class CommunityComment(Base):
    """CommunityPost 1건에 달리는 코멘트. DiagnosisComment와 동일한 모양 -
    누구나(농가/컨설턴트) 서로의 글에 코멘트를 남길 수 있다."""

    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False)

    author_type = Column(String(20), nullable=False)  # household / consultant / admin
    author_household_id = Column(Integer, ForeignKey("households.id"), nullable=True)
    author_consultant_id = Column(Integer, ForeignKey("consultant_users.id"), nullable=True)
    author_name = Column(String(50), nullable=False)

    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="visible")  # visible / hidden
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    post = relationship("CommunityPost", back_populates="comments")


class CommunityReport(Base):
    """게시글/댓글 신고. post_id/comment_id 중 하나만 채워진다. 같은 대상에 신고가
    임계치(REPORT_HIDE_THRESHOLD, community_service.py) 이상 쌓이면 자동으로
    status=hidden 처리되어 노출이 멈추고, 관리자가 검수 화면에서 최종 판단한다."""

    __tablename__ = "community_reports"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("community_comments.id"), nullable=True)
    reporter_household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    post = relationship("CommunityPost")
    comment = relationship("CommunityComment")


class AdministrativeRegion(Base):
    """전국 시/군/구 표준 목록(통계청/행정안전부 행정구역 기준). farm.region의 자유
    텍스트 입력값을 검증/정규화하기 위한 참고 테이블 - farms 테이블과 FK로 묶지는
    않는다. region은 계속 자유 문자열 컬럼으로 두고 "이 목록 중에서만 고르게" 만드는
    정도로 충분해서, farms 마이그레이션 없이 안전하게 추가할 수 있다.

    sigungu만으로는 전국 유일하지 않다(예: "중구"가 서울/부산/대구/인천/대전/울산에
    모두 있음) - 그래서 (sido, sigungu) 조합으로 유니크 제약을 건다. 시/도 자체가
    기초자치단체를 두지 않는 세종특별자치시는 sigungu에 시도명과 동일한 값을 넣어
    단일 행으로 표현한다."""

    __tablename__ = "administrative_regions"
    __table_args__ = (UniqueConstraint("sido", "sigungu", name="uq_sido_sigungu"),)

    id = Column(Integer, primary_key=True, index=True)
    sido = Column(String(20), nullable=False)
    sigungu = Column(String(30), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
