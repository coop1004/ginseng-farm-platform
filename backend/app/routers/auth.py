from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_household_id, get_current_user
from app.seed import get_ginseng_crop_id
from app.services.auth_service import (
    create_access_token,
    generate_join_code,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(db: Session, user: models.User, household: models.Household) -> schemas.TokenResponse:
    token = create_access_token(user.id)
    return schemas.TokenResponse(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
        household=schemas.HouseholdOut.model_validate(household),
    )


@router.post("/register/new-household", response_model=schemas.TokenResponse)
def register_new_household(payload: schemas.RegisterNewHousehold, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.phone == payload.phone).first():
        raise HTTPException(status_code=400, detail="이미 가입된 전화번호입니다.")

    join_code = generate_join_code()
    while db.query(models.Household).filter(models.Household.join_code == join_code).first():
        join_code = generate_join_code()

    household = models.Household(name=payload.household_name, join_code=join_code)
    db.add(household)
    db.flush()

    user = models.User(phone=payload.phone, name=payload.name, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()

    db.add(models.HouseholdMember(household_id=household.id, user_id=user.id))

    crop_ids = payload.crop_ids or [get_ginseng_crop_id(db)]  # 구버전 클라이언트는 crop_ids를 안 보냄 -> 인삼 기본값
    for crop_id in set(crop_ids):
        db.add(models.HouseholdCrop(household_id=household.id, crop_id=crop_id))

    db.commit()
    db.refresh(user)
    db.refresh(household)

    return _token_response(db, user, household)


@router.post("/register/join-household", response_model=schemas.TokenResponse)
def register_join_household(payload: schemas.RegisterJoinHousehold, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.phone == payload.phone).first():
        raise HTTPException(status_code=400, detail="이미 가입된 전화번호입니다.")

    household = (
        db.query(models.Household)
        .filter(models.Household.join_code == payload.join_code.strip().upper())
        .first()
    )
    if not household:
        raise HTTPException(status_code=404, detail="농가 코드를 찾을 수 없습니다. 코드를 다시 확인해주세요.")

    user = models.User(phone=payload.phone, name=payload.name, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()

    db.add(models.HouseholdMember(household_id=household.id, user_id=user.id))
    db.commit()
    db.refresh(user)

    return _token_response(db, user, household)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="전화번호 또는 비밀번호가 올바르지 않습니다.")

    membership = db.query(models.HouseholdMember).filter(models.HouseholdMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="소속된 농가가 없습니다. 관리자에게 문의해주세요.")

    household = db.query(models.Household).filter(models.Household.id == membership.household_id).first()
    return _token_response(db, user, household)


@router.get("/me", response_model=schemas.MeResponse)
def me(
    current_user: models.User = Depends(get_current_user),
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    member_rows = (
        db.query(models.User)
        .join(models.HouseholdMember, models.HouseholdMember.user_id == models.User.id)
        .filter(models.HouseholdMember.household_id == household_id)
        .all()
    )
    return schemas.MeResponse(
        user=schemas.UserOut.model_validate(current_user),
        household=schemas.HouseholdOut.model_validate(household),
        members=[schemas.UserOut.model_validate(m) for m in member_rows],
    )
