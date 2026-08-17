from typing import List

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.auth_service import (
    decode_access_token,
    decode_admin_access_token,
    decode_consultant_access_token,
)


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
    # 로그인 시점 이후에 정지/탈퇴 처리됐을 수 있으므로, 이미 발급된 토큰이라도 매 요청마다
    # 다시 확인한다 - 그래야 "로그인 즉시 차단"이 이미 로그인해둔 세션에도 적용된다.
    household = db.query(models.Household).filter(models.Household.id == membership.household_id).first()
    if household and household.status in ("suspended", "withdrawn"):
        raise HTTPException(status_code=403, detail="이용이 제한된 계정입니다. 관리자에게 문의해주세요.")
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


def get_current_consultant(
    authorization: str = Header(None), db: Session = Depends(get_db)
) -> models.ConsultantUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="컨설턴트 로그인이 필요합니다.")

    token = authorization[len("Bearer "):].strip()
    try:
        consultant_id = decode_consultant_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")

    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not consultant or not consultant.is_active:
        raise HTTPException(status_code=401, detail="컨설턴트 계정을 찾을 수 없습니다.")
    return consultant


def get_consultant_household_ids(
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    db: Session = Depends(get_db),
) -> List[int]:
    """로그인한 컨설턴트가 배정받은 담당 농가 id 목록. 컨설턴트가 시스템의 모든 농가가
    아니라 배정된 농가로만 접근할 수 있도록 라우터에서 공통으로 재사용한다."""
    rows = (
        db.query(models.ConsultantHousehold.household_id)
        .filter(models.ConsultantHousehold.consultant_id == current_consultant.id)
        .all()
    )
    return [r[0] for r in rows]


def ensure_consultant_farm_access(farm: models.Farm, consultant_household_ids: List[int]) -> None:
    if farm.household_id not in consultant_household_ids:
        raise HTTPException(status_code=404, detail="담당 농가의 농장이 아닙니다.")
