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
