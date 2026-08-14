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


def run_light_migrations():
    """Base.metadata.create_all은 새 테이블만 만들 뿐 기존 테이블에 컬럼을 추가하지
    않는다. 별도 마이그레이션 도구(alembic 등) 없이 운영 중이라, 이미 배포된 테이블에
    새 컬럼이 필요할 때는 여기서 존재 여부를 확인하고 없으면 ALTER TABLE로 추가한다."""
    inspector = inspect(engine)
    if "admin_users" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("admin_users")}
        if "is_protected" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE admin_users ADD COLUMN is_protected BOOLEAN NOT NULL DEFAULT 0"))
