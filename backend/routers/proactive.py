"""Plan-Quest — 능동적 추천 / 개인화 REST API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from proactive_ai import (
    get_proactive_suggestions,
    analyze_habit_pattern,
    build_personalization_context,
)

router = APIRouter(prefix="/api/proactive", tags=["능동AI"])


@router.get("/suggestions")
def suggestions(user_id: int = 1, db: Session = Depends(get_db)):
    """지금 사용자에게 보여줄 추천 / 알림 목록.

    프론트는 이 결과를 배지/토스트/푸시 등으로 표시.
    """
    return get_proactive_suggestions(db, user_id=user_id)


@router.get("/insights")
def insights(user_id: int = 1, db: Session = Depends(get_db)):
    """일정 달성 패턴 분석 결과."""
    return analyze_habit_pattern(db, user_id=user_id)


@router.get("/context")
def personalization_context(
    query: str = "",
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    """AI 프롬프트 주입용 개인화 컨텍스트 미리보기 (디버그)."""
    text = build_personalization_context(db, query, user_id=user_id)
    return {"context": text}
