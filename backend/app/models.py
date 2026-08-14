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


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # 최초(부트스트랩) 관리자 계정 표시. 이 계정은 다른 관리자가 삭제할 수 없다
    # (신규로 추가된 관리자가 실수/악의로 나머지 계정을 전부 지워 아무도 못 들어오는 상황 방지).
    is_protected = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


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
    name = Column(String(100), nullable=False)  # 농가명 (대표자/농가 이름)
    join_code = Column(String(10), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    members = relationship("HouseholdMember", back_populates="household", cascade="all, delete-orphan")
    farms = relationship("Farm", back_populates="household", cascade="all, delete-orphan")


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_household_user"),)

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    farm_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    region = Column(String(50), index=True)  # 시/군/구 단위 (지도/통계 그룹핑용)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_pyeong = Column(Float, default=0)
    area_m2 = Column(Float, default=0)
    facility_type = Column(String(20), default="노지")  # 노지 / 해가림 / 스마트팜
    cultivation_year = Column(Integer, default=1)  # 1~6년근
    phone = Column(String(30), nullable=True)
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household", back_populates="farms")
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
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)

    diagnosis_type = Column(String(20), nullable=False)  # 병해 / 해충 / 생리장애
    crop_name = Column(String(50), default="인삼")
    occurrence_date = Column(Date, default=dt.date.today)
    photo_path = Column(String(255), nullable=True)

    # EXIF로부터 추출한 정보
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    photo_taken_at = Column(DateTime, nullable=True)

    # OpenWeather 연동 결과
    weather_temp_c = Column(Float, nullable=True)
    weather_humidity_percent = Column(Float, nullable=True)
    weather_rainfall_mm = Column(Float, nullable=True)
    weather_wind_ms = Column(Float, nullable=True)
    weather_source = Column(String(20), nullable=True)  # api / demo

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

    farm = relationship("Farm", back_populates="diagnoses")
    notifications = relationship("Notification", back_populates="diagnosis")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=True)

    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    recommended_product = Column(String(150), nullable=True)
    sent_by = Column(String(50), default="관리자")
    status = Column(String(20), default="발송됨")  # 발송됨 / 확인됨
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
