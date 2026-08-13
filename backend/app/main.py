from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, diagnosis, farms, reports, stats, work_logs
from app.seed import seed_if_empty

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="인삼 농장 전용 AI 영농일지 앱 및 농자재 회사 모니터링 대시보드 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(farms.router)
app.include_router(work_logs.router)
app.include_router(diagnosis.router)
app.include_router(stats.router)
app.include_router(admin.router)
app.include_router(reports.router)


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "demo_mode": settings.demo_mode,
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
