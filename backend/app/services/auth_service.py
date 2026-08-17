import datetime as dt
import random
import string

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """토큰을 검증하고 user_id를 반환한다. 유효하지 않으면 jwt 관련 예외를 던진다."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return int(payload["sub"])


def create_admin_access_token(admin_id: int) -> str:
    """농가용 토큰과 클레임 이름을 다르게 하여(admin_sub), 농가 로그인 토큰이
    관리자 API에 잘못 쓰이거나 그 반대로 쓰이는 것을 원천적으로 막는다."""
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"admin_sub": str(admin_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_admin_access_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if "admin_sub" not in payload:
        raise jwt.InvalidTokenError("관리자 토큰이 아닙니다.")
    return int(payload["admin_sub"])


def create_consultant_access_token(consultant_id: int) -> str:
    """컨설턴트용 토큰도 admin과 마찬가지로 클레임 이름을 분리해서(consultant_sub)
    농가/관리자 토큰과 섞여 쓰이지 않게 한다."""
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"consultant_sub": str(consultant_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_consultant_access_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if "consultant_sub" not in payload:
        raise jwt.InvalidTokenError("컨설턴트 토큰이 아닙니다.")
    return int(payload["consultant_sub"])


def generate_join_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def generate_temp_password(length: int = 10) -> str:
    """관리자가 농가/컨설턴트 비밀번호를 초기화할 때 쓰는 임시 비밀번호. 전화로 불러줘야
    하므로 헷갈리는 문자(0/O, 1/l/I 등)는 알파벳에서 제외한다."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=length))
