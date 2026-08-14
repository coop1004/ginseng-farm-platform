from typing import List

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.auth_service import decode_access_token, decode_admin_access_token


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    token = authorization[len("Bearer "):].strip()
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user


def get_current_household_id(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    membership = (
        db.query(models.HouseholdMember)
        .filter(models.HouseholdMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="소속된 농가가 없습니다.")
    return membership.household_id


def ensure_farm_access(farm: models.Farm, household_id: int) -> None:
    if farm.household_id != household_id:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")


def get_household_crop_ids(
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
) -> List[int]:
    """로그인한 농가가 등록한(=화면에 노출받을) crop_id 목록. 병해충 참고자료, 농장 생성 등
    작물별로 접근을 제한해야 하는 라우터에서 공통으로 재사용한다."""
    rows = db.query(models.HouseholdCrop.crop_id).filter(models.HouseholdCrop.household_id == household_id).all()
    return [r[0] for r in rows]


def get_current_admin(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.AdminUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="관리자 로그인이 필요합니다.")

    token = authorization[len("Bearer "):].strip()
    try:
        admin_id = decode_admin_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")

    admin = db.query(models.AdminUser).filter(models.AdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=401, detail="관리자 계정을 찾을 수 없습니다.")
    return admin
