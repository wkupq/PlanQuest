"""Plan-Quest — AI 응답 피드백 시스템.

사용자가 AI 응답에 👍 / 👎 를 매김 → 메모리에 저장 → 다음 응답 개선.

흐름:
  1) 사용자가 AI 와 대화 (응답 받음)
  2) 응답에 대해 POST /api/feedback/rate { rating: "good" | "bad", message: ..., response: ... }
  3) 피드백을 RAG 메모리에 저장
     - good → high importance (0.8), memory_type=preference
     - bad  → low importance (0.2), 다음 응답에서 회피용 참고
  4) 다음 AI 응답 시 build_personalization_context() 가 자동 활용

엔드포인트:
  POST /api/feedback/rate    — 응답 평가 + 메모리 저장
  GET  /api/feedback/recent  — 최근 피드백 목록
  GET  /api/feedback/stats   — 통계 (👍 비율 등)
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import UserMemory


router = APIRouter(prefix="/api/feedback", tags=["피드백"])


class FeedbackRequest(BaseModel):
    rating: Literal["good", "bad"]
    user_message: str
    ai_response: str
    user_id: int = 1


@router.post("/rate")
def rate_response(req: FeedbackRequest, db: Session = Depends(get_db)):
    """AI 응답 평가 → 메모리 저장."""
    if req.rating == "good":
        importance = 0.8
        prefix = "[좋아한 응답]"
    else:
        importance = 0.2
        prefix = "[피해야 할 응답]"

    # 메모리에 저장 (ChromaDB + UserMemory 둘 다)
    try:
        from memory_engine import get_memory_engine
        engine = get_memory_engine()
        text = f"{prefix} Q: {req.user_message[:200]} → A: {req.ai_response[:300]}"
        chroma_id = None
        if engine.enabled:
            chroma_id = engine.add(
                user_id=req.user_id,
                text=text,
                memory_type="preference",
                importance=importance,
                metadata={"feedback_rating": req.rating},
                db=db,
            )
        return {
            "message": f"{'👍' if req.rating == 'good' else '👎'} 피드백 저장됨",
            "chroma_id": chroma_id,
            "importance": importance,
        }
    except Exception as e:
        raise HTTPException(500, f"피드백 저장 실패: {e}")


@router.get("/recent")
def recent_feedback(limit: int = 20, db: Session = Depends(get_db)):
    """최근 피드백 (UserMemory 의 preference 카테고리 중 feedback 표시 있는 것)."""
    rows = (
        db.query(UserMemory)
        .filter(UserMemory.memory_type == "preference")
        .filter(UserMemory.content.like("[좋아한 응답]%") | UserMemory.content.like("[피해야 할 응답]%"))
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        rating = "good" if "[좋아한 응답]" in r.content else "bad"
        out.append({
            "id": r.id,
            "rating": rating,
            "importance": r.importance_score,
            "content": r.content[:200],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.get("/stats")
def feedback_stats(db: Session = Depends(get_db)):
    """피드백 통계 (👍 비율, 최근 7일 추세 등)."""
    rows = (
        db.query(UserMemory)
        .filter(UserMemory.memory_type == "preference")
        .all()
    )

    good = sum(1 for r in rows if "[좋아한 응답]" in (r.content or ""))
    bad = sum(1 for r in rows if "[피해야 할 응답]" in (r.content or ""))
    total = good + bad

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_good = sum(
        1 for r in rows
        if "[좋아한 응답]" in (r.content or "")
        and r.created_at and r.created_at >= week_ago
    )
    recent_bad = sum(
        1 for r in rows
        if "[피해야 할 응답]" in (r.content or "")
        and r.created_at and r.created_at >= week_ago
    )

    return {
        "total_feedback": total,
        "good": good,
        "bad": bad,
        "satisfaction_rate": round(good / total, 2) if total else None,
        "recent_7d": {
            "good": recent_good,
            "bad": recent_bad,
            "satisfaction_rate": round(recent_good / (recent_good + recent_bad), 2) if (recent_good + recent_bad) else None,
        },
    }
