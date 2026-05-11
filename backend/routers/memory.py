"""Plan-Quest — 메모리 REST API.

엔드포인트:
  POST   /api/memory/add       — 메모리 1건 추가
  POST   /api/memory/search    — 의미 검색 (유사 맥락 top_k 반환)
  GET    /api/memory/stats     — 메모리 통계
  POST   /api/memory/cleanup   — 임계값 엔진 실행 (dry_run 옵션)
  DELETE /api/memory/{id}      — 메모리 1건 삭제
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from memory_engine import get_memory_engine, auto_categorize, auto_importance
from models import UserMemory

router = APIRouter(prefix="/api/memory", tags=["메모리"])


# ─── Pydantic 스키마 ────────────────────────────────────
class AddMemoryReq(BaseModel):
    text: str
    memory_type: str = Field(
        default="conversation",
        description="conversation | habit | preference | game_event",
    )
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    user_id: int = 1


class SearchMemoryReq(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=20)
    memory_type: Optional[str] = None
    user_id: int = 1


class CleanupReq(BaseModel):
    dry_run: bool = False


class MemoryItem(BaseModel):
    chroma_id: str
    text: str
    memory_type: str
    importance: float
    distance: Optional[float] = None


# ─── 엔드포인트 ─────────────────────────────────────────
@router.post("/add")
def add_memory(req: AddMemoryReq, db: Session = Depends(get_db)):
    """메모리 1건 추가."""
    engine = get_memory_engine()
    if not engine.enabled:
        raise HTTPException(503, "메모리 엔진이 비활성 상태입니다 (chromadb 또는 ollama 임베딩 미설치)")

    chroma_id = engine.add(
        user_id=req.user_id,
        text=req.text,
        memory_type=req.memory_type,
        importance=req.importance,
        db=db,
    )
    if not chroma_id:
        raise HTTPException(500, "메모리 추가 실패")

    return {"chroma_id": chroma_id, "message": "추가됨"}


@router.post("/search", response_model=List[MemoryItem])
def search_memory(req: SearchMemoryReq, db: Session = Depends(get_db)):
    """의미 기반 유사 메모리 검색."""
    engine = get_memory_engine()
    if not engine.enabled:
        return []

    results = engine.search(
        user_id=req.user_id,
        query=req.query,
        top_k=req.top_k,
        memory_type=req.memory_type,
        db=db,
    )
    return [MemoryItem(**r) for r in results]


@router.get("/stats")
def memory_stats(db: Session = Depends(get_db)):
    """메모리 통계 (총 개수, 종류별 분포)."""
    engine = get_memory_engine()
    base = engine.get_stats()

    # SQLite 메타에서 종류별 분포
    by_type = {}
    by_importance = {"high": 0, "mid": 0, "low": 0}
    if engine.enabled:
        rows = db.query(UserMemory).all()
        for r in rows:
            by_type[r.memory_type] = by_type.get(r.memory_type, 0) + 1
            if r.importance_score >= 0.7:
                by_importance["high"] += 1
            elif r.importance_score >= 0.4:
                by_importance["mid"] += 1
            else:
                by_importance["low"] += 1

    base["by_type"] = by_type
    base["by_importance"] = by_importance
    return base


@router.post("/cleanup")
def cleanup_memory(req: CleanupReq, db: Session = Depends(get_db)):
    """임계값 엔진 실행. 오래되고 덜 중요한 메모리 정리.

    dry_run=true 면 실제 삭제 안 하고 정리 대상만 반환.
    """
    engine = get_memory_engine()
    if not engine.enabled:
        raise HTTPException(503, "메모리 엔진 비활성")

    result = engine.cleanup(db, dry_run=req.dry_run)
    return result


# ─── W5 D3: 자동 카테고리화 ──────────────────────────────
class AutoAddReq(BaseModel):
    text: str
    user_id: int = 1


@router.post("/auto-add")
def auto_add(req: AutoAddReq, db: Session = Depends(get_db)):
    """카테고리 + 중요도 자동 부여하고 추가."""
    engine = get_memory_engine()
    if not engine.enabled:
        raise HTTPException(503, "메모리 엔진 비활성")

    cat = auto_categorize(req.text)
    imp = auto_importance(req.text, cat)
    chroma_id = engine.add(
        user_id=req.user_id,
        text=req.text,
        memory_type=cat,
        importance=imp,
        db=db,
    )
    return {
        "chroma_id": chroma_id,
        "auto_category": cat,
        "auto_importance": imp,
    }


@router.post("/recategorize")
def recategorize_all(db: Session = Depends(get_db)):
    """기존 모든 메모리에 자동 카테고리 + 중요도 재할당."""
    engine = get_memory_engine()
    if not engine.enabled:
        raise HTTPException(503, "메모리 엔진 비활성")

    rows = db.query(UserMemory).all()
    changed = 0
    for r in rows:
        new_cat = auto_categorize(r.content)
        new_imp = auto_importance(r.content, new_cat)
        if r.memory_type != new_cat or abs((r.importance_score or 0) - new_imp) > 0.05:
            r.memory_type = new_cat
            r.importance_score = new_imp
            changed += 1
    db.commit()
    return {"checked": len(rows), "changed": changed}


@router.delete("/{chroma_id}")
def delete_memory(chroma_id: str, db: Session = Depends(get_db)):
    """단건 삭제."""
    engine = get_memory_engine()
    if not engine.enabled:
        raise HTTPException(503, "메모리 엔진 비활성")

    # ChromaDB 에서
    try:
        engine.collection.delete(ids=[chroma_id])
    except Exception:
        pass

    # SQLite 에서
    row = db.query(UserMemory).filter_by(chroma_id=chroma_id).first()
    if row:
        db.delete(row)
        db.commit()

    return {"message": "삭제됨", "chroma_id": chroma_id}
