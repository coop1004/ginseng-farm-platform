from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine, run_light_migrations
from app.routers import (
    admin,
    auth,
    consultant,
    crops,
    diagnosis,
    farms,
    notifications,
    pest_reference,
    reference,
    reports,
    stats,
    weather,
    work_logs,
)
from app.seed import (
    backfill_crop_ids_if_missing,
    backfill_household_crops_if_missing,
    backfill_pest_disease_materials_if_missing,
    ensure_protected_admin,
    seed_admin_if_empty,
    seed_crops_if_empty,
    seed_demo_consultant_if_empty,
    seed_if_empty,
    seed_treatment_references_if_empty,
)
from app.seed_pilot_crops import seed_pilot_crop_pest_diseases_if_empty
from app.seed_regional_demo import seed_regional_pilot_crop_demo_if_empty

Base.metadata.create_all(bind=engine)
run_light_migrations()

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

app.include_router(auth.router)
app.include_router(farms.router)
app.include_router(work_logs.router)
app.include_router(diagnosis.router)
app.include_router(stats.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(weather.router)
app.include_router(weather.farmer_router)
app.include_router(reference.router)
app.include_router(crops.router)
app.include_router(pest_reference.router)
app.include_router(consultant.router)


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        seed_crops_if_empty(db)
        backfill_crop_ids_if_missing(db)
        seed_if_empty(db)
        seed_admin_if_empty(db)
        ensure_protected_admin(db)
        seed_treatment_references_if_empty(db)
        backfill_pest_disease_materials_if_missing(db)
        seed_pilot_crop_pest_diseases_if_empty(db)
        seed_regional_pilot_crop_demo_if_empty(db)
        backfill_household_crops_if_missing(db)
        seed_demo_consultant_if_empty(db)
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
