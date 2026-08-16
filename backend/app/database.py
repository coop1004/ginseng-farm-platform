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


def run_light_migrations():
    """Base.metadata.create_all은 새 테이블만 만들 뿐 기존 테이블에 컬럼을 추가하지
    않는다. 별도 마이그레이션 도구(alembic 등) 없이 운영 중이라, 이미 배포된 테이블에
    새 컬럼이 필요할 때는 여기서 존재 여부를 확인하고 없으면 ALTER TABLE로 추가한다."""
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
