from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_consultant
from app.services.auth_service import create_consultant_access_token, verify_password

router = APIRouter(prefix="/api/consultant", tags=["consultant"])


@router.post("/auth/login", response_model=schemas.ConsultantTokenResponse)
def consultant_login(payload: schemas.ConsultantLoginRequest, db: Session = Depends(get_db)):
    consultant = (
        db.query(models.ConsultantUser).filter(models.ConsultantUser.username == payload.username).first()
    )
    if not consultant or not consultant.is_active or not verify_password(payload.password, consultant.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_consultant_access_token(consultant.id)
    return schemas.ConsultantTokenResponse(
        access_token=token, consultant=schemas.ConsultantOut.model_validate(consultant)
    )


@router.get("/auth/me", response_model=schemas.ConsultantOut)
def consultant_me(current_consultant: models.ConsultantUser = Depends(get_current_consultant)):
    return schemas.ConsultantOut.model_validate(current_consultant)
