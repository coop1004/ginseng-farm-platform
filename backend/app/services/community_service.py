"""커뮤니티 게시글/댓글/신고 공용 로직. 농가용(routers/diagnosis.py 확장 또는 신규
routers/community.py)과 컨설턴트용 라우터가 동일한 생성/조회/신고 절차를 공유한다.

공개범위(visibility) 판단은 organization 테이블이 없는 대신 이미 존재하는
ConsultantHousehold(컨설턴트 담당 농가 배정) 매핑을 그대로 재사용한다 - "같은 컨설턴트가
담당하는 농가끼리만" 범위를 새 테이블 없이 표현할 수 있다."""
import json
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.diagnosis_service import initial_photo_paths

REPORT_HIDE_THRESHOLD = 3


def get_household_consultant_ids(db: Session, household_id: int) -> List[int]:
    rows = (
        db.query(models.ConsultantHousehold.consultant_id)
        .filter(models.ConsultantHousehold.household_id == household_id)
        .all()
    )
    return [r[0] for r in rows]


def get_households_sharing_consultant(db: Session, household_id: int) -> List[int]:
    """household_id와 담당 컨설턴트를 하나라도 공유하는 농가 id 목록(본인 포함).
    consultant_scope 글의 "같은 컨설턴트 담당 농가끼리만" 범위를 계산하는 데 쓴다."""
    consultant_ids = get_household_consultant_ids(db, household_id)
    if not consultant_ids:
        return [household_id]
    rows = (
        db.query(models.ConsultantHousehold.household_id)
        .filter(models.ConsultantHousehold.consultant_id.in_(consultant_ids))
        .distinct()
        .all()
    )
    ids = {r[0] for r in rows}
    ids.add(household_id)
    return list(ids)


def to_post_response(post: models.CommunityPost, include_comments: bool = False) -> dict:
    visible_comments = [c for c in post.comments if c.status == "visible"]
    data = {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "photo_paths": json.loads(post.photo_paths_json) if post.photo_paths_json else [],
        "kind": post.kind,
        "crop_id": post.crop_id,
        "crop_name": post.crop.name_kr if post.crop else None,
        "diagnosis_id": post.diagnosis_id,
        "visibility": post.visibility,
        "author_type": post.author_type,
        "author_name": post.author_name,
        "status": post.status,
        "comment_count": len(visible_comments),
        "created_at": post.created_at,
    }
    if include_comments:
        data["comments"] = visible_comments
    return data


def is_post_visible_to_household(
    post: models.CommunityPost, household_id: int, peer_household_ids: List[int], my_consultant_ids: List[int]
) -> bool:
    if post.visibility == "public":
        return True
    if post.author_type == "consultant":
        return post.author_consultant_id in my_consultant_ids
    if post.author_type == "household":
        return post.author_household_id in peer_household_ids
    return post.author_household_id == household_id


def ensure_post_visible_to_household(db: Session, post: models.CommunityPost, household_id: int) -> bool:
    peer_household_ids = get_households_sharing_consultant(db, household_id)
    my_consultant_ids = get_household_consultant_ids(db, household_id)
    return is_post_visible_to_household(post, household_id, peer_household_ids, my_consultant_ids)


def list_posts_for_household(
    db: Session, household_id: int, crop_id: Optional[int] = None, kind: Optional[str] = None
) -> List[models.CommunityPost]:
    peer_household_ids = get_households_sharing_consultant(db, household_id)
    my_consultant_ids = get_household_consultant_ids(db, household_id)

    query = db.query(models.CommunityPost).filter(models.CommunityPost.status == "visible")
    if crop_id:
        query = query.filter(models.CommunityPost.crop_id == crop_id)
    if kind:
        query = query.filter(models.CommunityPost.kind == kind)
    posts = query.order_by(models.CommunityPost.created_at.desc()).all()
    return [p for p in posts if is_post_visible_to_household(p, household_id, peer_household_ids, my_consultant_ids)]


def is_post_visible_to_consultant(post: models.CommunityPost, consultant_id: int, household_ids: List[int]) -> bool:
    if post.visibility == "public":
        return True
    if post.author_type == "consultant":
        return post.author_consultant_id == consultant_id
    if post.author_type == "household":
        return post.author_household_id in household_ids
    return False


def list_posts_for_consultant(
    db: Session, consultant_id: int, household_ids: List[int], crop_id: Optional[int] = None, kind: Optional[str] = None
) -> List[models.CommunityPost]:
    query = db.query(models.CommunityPost).filter(models.CommunityPost.status == "visible")
    if crop_id:
        query = query.filter(models.CommunityPost.crop_id == crop_id)
    if kind:
        query = query.filter(models.CommunityPost.kind == kind)
    posts = query.order_by(models.CommunityPost.created_at.desc()).all()
    return [p for p in posts if is_post_visible_to_consultant(p, consultant_id, household_ids)]


def create_channel_post(
    db: Session,
    consultant: models.ConsultantUser,
    title: str,
    body: Optional[str],
    crop_id: Optional[int],
    visibility: str,
) -> models.CommunityPost:
    post = models.CommunityPost(
        title=title,
        body=body,
        kind="channel",
        crop_id=crop_id,
        visibility=visibility if visibility in ("public", "consultant_scope") else "consultant_scope",
        author_type="consultant",
        author_consultant_id=consultant.id,
        author_name=consultant.name,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def create_diagnosis_share(
    db: Session,
    household: models.Household,
    diagnosis: models.Diagnosis,
    title: str,
    body: Optional[str],
    visibility: str,
) -> models.CommunityPost:
    """농가가 본인 진단을 옵트인으로 커뮤니티에 공유한다. 원본 Diagnosis 행은 건드리지
    않고 새 게시글을 만드는 방식이라, 이 함수가 호출되기 전까지는 어떤 진단도 공개되지
    않는다. 정확한 GPS/위치 정보는 절대 복사하지 않는다(개인정보 보호)."""
    # 커뮤니티에는 등록 시점 피해 사진(initial)만 공유한다 - 방제 경과 기록(followup)은
    # 사진이 없을 수도 있고(공유 시 photo_paths_json에 null이 섞이는 문제), 농가가 이
    # 진단을 공유하기로 선택한 시점 이후에 남긴 후속 사진까지 자동으로 공개되는 것도
    # 의도한 동작이 아니다.
    photo_paths = initial_photo_paths(diagnosis) or ([diagnosis.photo_path] if diagnosis.photo_path else [])
    post = models.CommunityPost(
        title=title,
        body=body,
        photo_paths_json=json.dumps(photo_paths, ensure_ascii=False),
        kind="diagnosis_share",
        crop_id=diagnosis.farm.crop_id if diagnosis.farm else None,
        diagnosis_id=diagnosis.id,
        visibility=visibility if visibility in ("public", "consultant_scope") else "public",
        author_type="household",
        author_household_id=household.id,
        author_name=household.name,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def add_comment(
    db: Session,
    post: models.CommunityPost,
    author_type: str,
    author_name: str,
    body: str,
    author_household_id: Optional[int] = None,
    author_consultant_id: Optional[int] = None,
) -> models.CommunityComment:
    comment = models.CommunityComment(
        post_id=post.id,
        author_type=author_type,
        author_name=author_name,
        author_household_id=author_household_id,
        author_consultant_id=author_consultant_id,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def report_post(db: Session, post: models.CommunityPost, reporter_household_id: int, reason: Optional[str]) -> models.CommunityReport:
    existing = (
        db.query(models.CommunityReport)
        .filter(
            models.CommunityReport.post_id == post.id,
            models.CommunityReport.reporter_household_id == reporter_household_id,
        )
        .first()
    )
    if existing:
        return existing

    report = models.CommunityReport(post_id=post.id, reporter_household_id=reporter_household_id, reason=reason)
    db.add(report)
    db.commit()

    count = db.query(models.CommunityReport).filter(models.CommunityReport.post_id == post.id).count()
    if count >= REPORT_HIDE_THRESHOLD and post.status == "visible":
        post.status = "hidden"
        db.commit()
    db.refresh(report)
    return report


def report_comment(
    db: Session, comment: models.CommunityComment, reporter_household_id: int, reason: Optional[str]
) -> models.CommunityReport:
    existing = (
        db.query(models.CommunityReport)
        .filter(
            models.CommunityReport.comment_id == comment.id,
            models.CommunityReport.reporter_household_id == reporter_household_id,
        )
        .first()
    )
    if existing:
        return existing

    report = models.CommunityReport(comment_id=comment.id, reporter_household_id=reporter_household_id, reason=reason)
    db.add(report)
    db.commit()

    count = db.query(models.CommunityReport).filter(models.CommunityReport.comment_id == comment.id).count()
    if count >= REPORT_HIDE_THRESHOLD and comment.status == "visible":
        comment.status = "hidden"
        db.commit()
    db.refresh(report)
    return report
