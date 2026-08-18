import datetime as dt

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(inspector, table: str, column: str, ddl_type: str) -> None:
    if table not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column not in columns:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def _relax_diagnosis_photos_photo_path_nullable() -> None:
    """diagnosis_photos.photo_path가 기존에 NOT NULL이면(구버전 스키마), SQLite가
    ALTER TABLE로 컬럼 제약을 직접 풀 수 없으므로(ALTER COLUMN 미지원) 테이블을
    통째로 재생성해 nullable로 바꾼다. 방제 경과 기록(followup)은 사진 없이 자가평가만
    남기는 경우도 있어야 하기 때문에 필요하다 - 새로 만들어진 DB는 모델 정의상 이미
    nullable이라 아무 것도 하지 않고 바로 반환한다."""
    inspector = inspect(engine)
    if "diagnosis_photos" not in inspector.get_table_names():
        return
    col = next((c for c in inspector.get_columns("diagnosis_photos") if c["name"] == "photo_path"), None)
    if col is None or col["nullable"]:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE diagnosis_photos RENAME TO diagnosis_photos_old"))
        conn.execute(
            text(
                """
                CREATE TABLE diagnosis_photos (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    diagnosis_id INTEGER NOT NULL,
                    photo_path VARCHAR(255),
                    created_at DATETIME,
                    FOREIGN KEY(diagnosis_id) REFERENCES diagnoses (id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO diagnosis_photos (id, diagnosis_id, photo_path, created_at)
                SELECT id, diagnosis_id, photo_path, created_at FROM diagnosis_photos_old
                """
            )
        )
        conn.execute(text("DROP TABLE diagnosis_photos_old"))


def backfill_farm_cultivation_start_date() -> None:
    """기존 cultivation_year(레거시 "N년근")만 있고 정확한 정식일이 없는 농장은,
    "오늘 연도 - cultivation_year + 1"년의 4월 1일(봄 정식 시기 관행에 맞춘 임의 날짜)로
    cultivation_start_date를 근사 채움하고 cultivation_start_date_estimated=True로
    표시해 농가가 나중에 정확한 날짜로 고치도록 안내한다. 이미 채워진 농장(신규 등록·
    이미 백필됨)은 건드리지 않아 재실행해도 안전하다."""
    inspector = inspect(engine)
    if "farms" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("farms")}
    if "cultivation_start_date" not in columns or "cultivation_year" not in columns:
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, cultivation_year FROM farms "
                "WHERE cultivation_start_date IS NULL AND cultivation_year IS NOT NULL"
            )
        ).fetchall()
        today_year = dt.date.today().year
        for farm_id, cultivation_year in rows:
            start_year = today_year - cultivation_year + 1
            approx_date = dt.date(start_year, 4, 1)
            conn.execute(
                text(
                    "UPDATE farms SET cultivation_start_date = :d, cultivation_start_date_estimated = 1 "
                    "WHERE id = :id"
                ),
                {"d": approx_date.isoformat(), "id": farm_id},
            )


def run_light_migrations():
    """Base.metadata.create_all은 새 테이블만 만들 뿐 기존 테이블에 컬럼을 추가하지
    않는다. 별도 마이그레이션 도구(alembic 등) 없이 운영 중이라, 이미 배포된 테이블에
    새 컬럼이 필요할 때는 여기서 존재 여부를 확인하고 없으면 ALTER TABLE로 추가한다."""
    # 컬럼 추가(_add_column_if_missing)보다 먼저, 테이블 재생성이 필요한 처리부터 끝낸다.
    _relax_diagnosis_photos_photo_path_nullable()
    inspector = inspect(engine)
    _add_column_if_missing(inspector, "admin_users", "is_protected", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(inspector, "notifications", "broadcast_group", "VARCHAR(40)")
    _add_column_if_missing(inspector, "diagnoses", "final_disease_name", "VARCHAR(100)")
    _add_column_if_missing(inspector, "diagnoses", "final_diagnosis_source", "VARCHAR(20)")
    _add_column_if_missing(inspector, "diagnoses", "final_diagnosis_note", "TEXT")
    _add_column_if_missing(inspector, "diagnoses", "final_diagnosis_by", "VARCHAR(50)")
    _add_column_if_missing(inspector, "diagnoses", "final_diagnosis_at", "DATETIME")
    _add_column_if_missing(inspector, "farms", "crop_id", "INTEGER")
    _add_column_if_missing(inspector, "farms", "growth_stage_id", "INTEGER")
    _add_column_if_missing(inspector, "treatment_references", "crop_id", "INTEGER")
    _add_column_if_missing(inspector, "treatment_references", "is_sample_data", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(inspector, "treatment_references", "photo_path", "VARCHAR(255)")
    _add_column_if_missing(inspector, "diagnoses", "created_by_type", "VARCHAR(20) NOT NULL DEFAULT 'household'")
    _add_column_if_missing(inspector, "diagnoses", "created_by_consultant_id", "INTEGER")
    # organization_id: 여러 회원사(농자재회사/컨설턴트그룹 등) 확장을 대비한 준비 작업.
    # NOT NULL DEFAULT 1로 추가하면 SQLite가 기존 행 전체를 즉시 채워준다(별도 백필 스크립트
    # 불필요) - 1은 seed.seed_default_organization_if_empty가 가장 먼저 만드는 "농자재회사A"의 id
    # (models.DEFAULT_ORGANIZATION_ID)와 반드시 일치해야 한다.
    _add_column_if_missing(inspector, "households", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "farms", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "diagnoses", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "notifications", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "consultant_households", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "consultant_users", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "admin_users", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    # 병해충·자재 CMS 정리: 병해충정보(treatment_references)는 공용으로 유지하고, 자재
    # 카탈로그(agri_materials)와 병해충↔자재 매핑(pest_disease_materials)에만 붙인다.
    _add_column_if_missing(inspector, "agri_materials", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(inspector, "pest_disease_materials", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    # 사진 EXIF에 GPS/촬영시각이 없을 때 대체값(농장 등록 주소/업로드 시각)을 썼는지 표시.
    _add_column_if_missing(inspector, "diagnoses", "gps_estimated", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(inspector, "diagnoses", "photo_taken_at_estimated", "BOOLEAN NOT NULL DEFAULT 0")
    # 플랫폼 운영자(찬파트너스, 조직 넘나들며 관리) vs 조직 전용 계정 구분. 기존 관리자는
    # 전부 platform_super로 취급하는 게 맞다고 조사로 확인됨(무제한 접근·전사 통계·"사내
    # 담당자 전용" 가입 절차 등 전부 platform_super 성격과 일치) - DEFAULT로 즉시 백필된다.
    _add_column_if_missing(inspector, "admin_users", "role", "VARCHAR(20) NOT NULL DEFAULT 'platform_super'")
    # 관리자가 컨설턴트 정보를 대신 수정할 수 있게 하는 작업의 일부 - 기존엔 연락처를
    # 저장할 컬럼 자체가 없었다.
    _add_column_if_missing(inspector, "consultant_users", "phone", "VARCHAR(30)")
    # 계정 정지/탈퇴 처리 - 기존 농가는 전부 active로 즉시 백필된다.
    _add_column_if_missing(inspector, "households", "status", "VARCHAR(20) NOT NULL DEFAULT 'active'")
    # 진단 경과 기록(방제 전/후 사진 + 자가평가). DEFAULT 'initial'로 추가하면 기존에
    # 저장돼 있던 사진들(전부 등록 시점 사진)이 자동으로 phase="initial"로 백필된다.
    _add_column_if_missing(inspector, "diagnosis_photos", "phase", "VARCHAR(20) NOT NULL DEFAULT 'initial'")
    _add_column_if_missing(inspector, "diagnosis_photos", "outcome", "VARCHAR(10)")
    _add_column_if_missing(inspector, "diagnosis_photos", "note", "TEXT")
    _add_column_if_missing(inspector, "diagnosis_photos", "days_since_treatment", "INTEGER")
    # 인삼 재배연차 자동계산(정식일 기준) - cultivation_year(레거시)는 폴백용으로 유지.
    _add_column_if_missing(inspector, "farms", "cultivation_start_date", "DATE")
    _add_column_if_missing(inspector, "farms", "cultivation_start_date_estimated", "BOOLEAN NOT NULL DEFAULT 0")
    # 농장 소프트 삭제 - 하드 삭제 시 cascade로 사라지는 Diagnosis/WorkLog 이력을 보존하기 위함.
    _add_column_if_missing(inspector, "farms", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
    backfill_farm_cultivation_start_date()
