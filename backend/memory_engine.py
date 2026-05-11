"""
Plan-Quest — RAG 메모리 엔진 (ChromaDB + Ollama Embeddings)

역할:
  사용자의 대화/습관/선호도/게임 이벤트를 벡터로 저장하고,
  새 질문이 들어오면 의미상 유사한 과거 맥락을 검색해서 AI 응답에 주입.

ChromaDB 는 로컬 SQLite 기반으로 동작 (~/chroma_db).
임베딩은 Ollama 의 nomic-embed-text 모델 사용 (작고 빠름).

임계값 엔진:
  - importance_score < 0.3 + 30일 이상 + 최근 7일간 access 0회 → 정리
  - 중요도가 높거나 자주 참조된 메모리는 영구 보존
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

# ChromaDB / 임베딩 — 모듈 미설치 시 graceful fallback
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    from langchain_community.embeddings import OllamaEmbeddings
    HAS_OLLAMA_EMB = True
except ImportError:
    try:
        from langchain.embeddings import OllamaEmbeddings  # 구버전
        HAS_OLLAMA_EMB = True
    except ImportError:
        HAS_OLLAMA_EMB = False


# ─── 설정 ─────────────────────────────────────────────────
CHROMA_DIR = os.path.join(os.path.expanduser("~"), "chroma_db")
COLLECTION_NAME = "plan_quest_memory"

EMBEDDING_MODEL = "nomic-embed-text"   # ollama pull nomic-embed-text 필요
EMBEDDING_FALLBACK = "qwen2.5:latest"  # nomic 없으면 LLM 임베딩

# 임계값 엔진
IMPORTANCE_CUTOFF = 0.3         # 이 미만은 정리 후보
DAYS_BEFORE_CLEANUP = 30        # 30일 지나야 정리 후보
RECENT_ACCESS_PROTECT = 7       # 최근 N일간 access 있으면 보호


class MemoryEngine:
    """ChromaDB 기반 사용자 맥락 메모리.

    사용:
        engine = MemoryEngine()
        engine.add(user_id=1, text="오늘 운동을 마쳤다", memory_type="habit", importance=0.6)
        results = engine.search(user_id=1, query="운동 어떻게 됐어?", top_k=3)
    """

    def __init__(self):
        self.enabled = HAS_CHROMA and HAS_OLLAMA_EMB
        if not self.enabled:
            print("[MemoryEngine] ChromaDB 또는 Ollama embeddings 미설치 → 메모리 기능 비활성")
            print("    pip install chromadb langchain-community")
            self.client = None
            self.collection = None
            self.embedder = None
            return

        os.makedirs(CHROMA_DIR, exist_ok=True)

        # 영속 클라이언트 (~/chroma_db 에 저장)
        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Plan-Quest user memory"},
        )

        # 임베딩 모델 (Ollama)
        try:
            self.embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)
            # 한 번 호출해서 사용 가능 확인
            _ = self.embedder.embed_query("테스트")
        except Exception:
            print(f"[MemoryEngine] {EMBEDDING_MODEL} 미설치 → {EMBEDDING_FALLBACK} 사용")
            try:
                self.embedder = OllamaEmbeddings(model=EMBEDDING_FALLBACK)
                _ = self.embedder.embed_query("테스트")
            except Exception as e:
                print(f"[MemoryEngine] Ollama 임베딩 실패: {e} → 메모리 기능 비활성")
                self.enabled = False
                return

        print(f"[MemoryEngine] 활성. 저장소: {CHROMA_DIR}, 모델: {self.embedder.model}")

    # ─── 저장 ──────────────────────────────────────────
    def add(
        self,
        user_id: int,
        text: str,
        memory_type: str = "conversation",
        importance: float = 0.5,
        metadata: Optional[Dict] = None,
        db: Optional[Session] = None,
    ) -> Optional[str]:
        """메모리 추가. 반환값: chroma_id (실패 시 None)."""
        if not self.enabled:
            return None

        chroma_id = f"mem_{user_id}_{uuid.uuid4().hex[:12]}"
        meta = {
            "user_id": user_id,
            "memory_type": memory_type,
            "importance": importance,
            "created_at": datetime.utcnow().isoformat(),
        }
        if metadata:
            # ChromaDB 는 nested 안 받음 → 플랫만
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

        try:
            embedding = self.embedder.embed_query(text)
            self.collection.add(
                ids=[chroma_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[meta],
            )

            # SQLite 메타 테이블에도 기록 (importance 임계값 엔진용)
            if db is not None:
                from models import UserMemory
                row = UserMemory(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=text,
                    chroma_id=chroma_id,
                    importance_score=importance,
                )
                db.add(row)
                db.commit()

            return chroma_id
        except Exception as e:
            print(f"[MemoryEngine.add] 실패: {e}")
            return None

    # ─── 검색 ──────────────────────────────────────────
    def search(
        self,
        user_id: int,
        query: str,
        top_k: int = 3,
        memory_type: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> List[Dict]:
        """유사한 과거 맥락 검색.

        Returns:
            [{"text": ..., "memory_type": ..., "importance": ..., "distance": ...}, ...]
        """
        if not self.enabled:
            return []

        try:
            embedding = self.embedder.embed_query(query)

            # ChromaDB where 절: 같은 user 만, optionally 같은 type 만
            where = {"user_id": user_id}
            if memory_type:
                where["memory_type"] = memory_type

            res = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where,
            )

            # 결과 정리
            output = []
            ids = (res.get("ids") or [[]])[0]
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]

            for i, doc in enumerate(docs):
                meta = metas[i] if i < len(metas) else {}
                output.append({
                    "chroma_id": ids[i] if i < len(ids) else "",
                    "text": doc,
                    "memory_type": meta.get("memory_type", "unknown"),
                    "importance": meta.get("importance", 0.5),
                    "distance": dists[i] if i < len(dists) else None,
                })

            # 검색된 메모리는 access_count 증가 (보호 효과)
            if db is not None and output:
                from models import UserMemory
                from sqlalchemy import update
                ids_list = [r["chroma_id"] for r in output if r["chroma_id"]]
                if ids_list:
                    rows = db.query(UserMemory).filter(
                        UserMemory.chroma_id.in_(ids_list)
                    ).all()
                    for r in rows:
                        r.access_count = (r.access_count or 0) + 1
                        r.last_accessed = datetime.utcnow()
                    db.commit()

            return output
        except Exception as e:
            print(f"[MemoryEngine.search] 실패: {e}")
            return []

    # ─── 컨텍스트 생성 (AI 주입용) ─────────────────────
    def build_context(self, user_id: int, query: str, top_k: int = 3, db=None) -> str:
        """AI 프롬프트에 주입할 형태의 텍스트 생성."""
        results = self.search(user_id, query, top_k=top_k, db=db)
        if not results:
            return ""

        lines = ["[과거 관련 맥락]"]
        for r in results:
            lines.append(f"- ({r['memory_type']}) {r['text']}")
        lines.append("")
        return "\n".join(lines)

    # ─── 임계값 엔진 (정리) ────────────────────────────
    def cleanup(self, db: Session, dry_run: bool = False) -> Dict:
        """오래되고 덜 중요한 메모리 정리.

        기준:
          importance < 0.3
          AND created_at < (오늘 - 30일)
          AND (last_accessed is None OR last_accessed < 오늘 - 7일)

        Returns:
            {"checked": N, "deleted": M, "ids": [...]}
        """
        if not self.enabled:
            return {"checked": 0, "deleted": 0, "ids": []}

        from models import UserMemory

        cutoff_old = datetime.utcnow() - timedelta(days=DAYS_BEFORE_CLEANUP)
        cutoff_recent = datetime.utcnow() - timedelta(days=RECENT_ACCESS_PROTECT)

        candidates = db.query(UserMemory).filter(
            UserMemory.importance_score < IMPORTANCE_CUTOFF,
            UserMemory.created_at < cutoff_old,
        ).all()

        deleted_ids = []
        for row in candidates:
            # 최근에 접근된 건 보호
            if row.last_accessed and row.last_accessed > cutoff_recent:
                continue

            deleted_ids.append(row.chroma_id)
            if not dry_run:
                # ChromaDB 에서 제거
                try:
                    if row.chroma_id:
                        self.collection.delete(ids=[row.chroma_id])
                except Exception:
                    pass
                db.delete(row)

        if not dry_run:
            db.commit()

        return {
            "checked": len(candidates),
            "deleted": len(deleted_ids),
            "ids": deleted_ids,
            "dry_run": dry_run,
        }

    def get_stats(self) -> Dict:
        """메모리 통계."""
        if not self.enabled:
            return {"enabled": False, "count": 0}
        try:
            count = self.collection.count()
            return {
                "enabled": True,
                "count": count,
                "storage": CHROMA_DIR,
                "model": self.embedder.model if self.embedder else None,
            }
        except Exception as e:
            return {"enabled": False, "error": str(e)}


# ─── 자동 카테고리화 (W5 D3) ─────────────────────────────
# 키워드 기반 분류. LLM 없이도 즉시 동작.
CATEGORY_KEYWORDS = {
    "habit":      ["운동", "공부", "스터디", "독서", "명상", "습관", "루틴", "완료", "달성"],
    "preference": ["좋아", "싫어", "선호", "취향", "원해", "싫", "보통", "관심"],
    "schedule":   ["일정", "약속", "회의", "미팅", "예정", "내일", "오늘", "다음", "스케줄"],
    "game_event": ["캐릭터", "구매", "배치", "수확", "하트", "레벨", "정원", "나무", "씨앗"],
    "emotion":    ["기쁘", "슬프", "힘들", "지치", "행복", "스트레스", "기분", "걱정", "불안"],
    "personal":   ["이름", "나이", "직업", "생일", "가족", "친구", "회사", "학교"],
}


def auto_categorize(text: str, default: str = "conversation") -> str:
    """텍스트에서 가장 매치되는 카테고리 자동 선택.

    각 카테고리별 키워드 매치 수를 세고, 최다 카테고리 반환.
    매치 0이면 default.
    """
    if not text:
        return default
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        s = sum(1 for kw in keywords if kw in text_lower)
        if s > 0:
            scores[cat] = s
    if not scores:
        return default
    return max(scores, key=scores.get)


def auto_importance(text: str, memory_type: str) -> float:
    """텍스트 + 카테고리 기반 중요도 자동 산정 (0.0 ~ 1.0).

    규칙:
      - personal/preference: 0.7 (장기 보존)
      - emotion/game_event:  0.5
      - schedule:           0.4 (시간 지나면 의미 없음)
      - habit:              0.5
      - conversation:       0.3 (기본)
      + 길이 보정 (50자 이상이면 +0.1)
      + 강조 단어 ("중요", "꼭", "절대") 있으면 +0.15
    """
    base = {
        "personal": 0.7, "preference": 0.7,
        "emotion": 0.5, "game_event": 0.5, "habit": 0.5,
        "schedule": 0.4,
        "conversation": 0.3,
    }.get(memory_type, 0.3)

    if text and len(text) >= 50:
        base += 0.1
    if text and any(kw in text for kw in ["중요", "꼭", "절대", "잊지", "기억"]):
        base += 0.15

    return min(1.0, base)


# ─── 싱글톤 ─────────────────────────────────────────────
_engine: Optional[MemoryEngine] = None


def get_memory_engine() -> MemoryEngine:
    global _engine
    if _engine is None:
        _engine = MemoryEngine()
    return _engine
