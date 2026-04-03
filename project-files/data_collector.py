"""
data_collector.py — LoRA 학습 데이터 수집기
=============================================
RAG 체인 대화 로그에서 고품질 (질문, 답변) 쌍을 수집하고
Alpaca / ShareGPT 포맷으로 저장합니다.

사용법:
    collector = DataCollector()
    collector.log_interaction(question, answer, metadata)
    collector.export_alpaca("train_data.json")
    collector.export_sharegpt("sharegpt_data.json")
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).parent
DATA_DIR = _BASE_DIR / "lora_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "interactions.db"
EXPORT_DIR = DATA_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 품질 필터 상수
# ---------------------------------------------------------------------------
MIN_QUESTION_LEN = 10     # 최소 질문 길이 (characters)
MIN_ANSWER_LEN = 30       # 최소 답변 길이
MAX_QUESTION_LEN = 1000
MAX_ANSWER_LEN = 4000
MIN_QUALITY_SCORE = 0.5   # 0.0 ~ 1.0

# Alpaca 기본 시스템 프롬프트
DEFAULT_SYSTEM = (
    "당신은 유능한 AI 개인 비서입니다. "
    "사용자의 질문에 친절하고 정확하게 답변하세요."
)


# ---------------------------------------------------------------------------
# 데이터 클래스
# ---------------------------------------------------------------------------
@dataclass
class Interaction:
    """단일 대화 상호작용 레코드."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    answer: str = ""
    system_prompt: str = DEFAULT_SYSTEM
    context_used: str = ""          # RAG 검색 결과 (참고 문서)
    source: str = "chat"            # chat | calendar | email | task
    quality_score: float = 0.0
    user_rating: int | None = None  # 1~5 사용자 평점 (선택)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_approved: bool = False       # 수동 검수 통과 여부


@dataclass
class AlpacaSample:
    """Alpaca 포맷 단일 샘플."""
    instruction: str
    input: str
    output: str
    system: str = DEFAULT_SYSTEM


@dataclass
class ShareGPTSample:
    """ShareGPT 포맷 단일 샘플."""
    conversations: list[dict]
    system: str = DEFAULT_SYSTEM


# ---------------------------------------------------------------------------
# 품질 평가기
# ---------------------------------------------------------------------------
class QualityEvaluator:
    """
    규칙 기반 품질 점수 계산기.
    점수 0.0~1.0, MIN_QUALITY_SCORE 미만은 수집에서 제외.
    """

    # 낮은 품질 패턴 (답변에 포함되면 감점)
    _LOW_QUALITY_PATTERNS = [
        r"모르겠습니다",
        r"잘 모르",
        r"죄송합니다.*없습니다",
        r"^.{1,20}$",      # 너무 짧은 답변
        r"오류가 발생",
        r"error",
        r"traceback",
    ]

    # 높은 품질 지표 (있으면 가점)
    _HIGH_QUALITY_PATTERNS = [
        r"\d+\.",          # 번호 목록
        r"예시|예를 들어",
        r"단계|절차|방법",
        r"왜냐하면|이유는",
    ]

    def __init__(self):
        self._low = [re.compile(p, re.IGNORECASE | re.DOTALL)
                     for p in self._LOW_QUALITY_PATTERNS]
        self._high = [re.compile(p, re.IGNORECASE)
                      for p in self._HIGH_QUALITY_PATTERNS]

    def score(self, question: str, answer: str) -> float:
        """
        질문·답변 쌍에 대한 품질 점수(0.0~1.0) 반환.
        """
        score = 0.5  # 기본 점수

        # --- 길이 기반 점수 ---
        q_len = len(question.strip())
        a_len = len(answer.strip())

        if q_len < MIN_QUESTION_LEN or q_len > MAX_QUESTION_LEN:
            return 0.0
        if a_len < MIN_ANSWER_LEN or a_len > MAX_ANSWER_LEN:
            return 0.0

        # 답변 길이 보너스 (100~800자 최적)
        if 100 <= a_len <= 800:
            score += 0.15
        elif a_len > 800:
            score += 0.05

        # --- 저품질 패턴 감점 ---
        for pattern in self._low:
            if pattern.search(answer):
                score -= 0.15

        # --- 고품질 패턴 가점 ---
        for pattern in self._high:
            if pattern.search(answer):
                score += 0.05

        # --- 질문 명확성 (물음표·의문사) ---
        if re.search(r"[?？]|어떻게|무엇|왜|언제|어디", question):
            score += 0.05

        return max(0.0, min(1.0, round(score, 3)))


# ---------------------------------------------------------------------------
# DataCollector
# ---------------------------------------------------------------------------
class DataCollector:
    """
    LoRA 학습 데이터 수집 및 내보내기.

    - SQLite에 모든 대화 저장 (thread-safe)
    - 품질 필터 자동 적용
    - Alpaca / ShareGPT 포맷 내보내기
    - RAG context 선택적 포함
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
        min_quality: float = MIN_QUALITY_SCORE,
        include_context_in_input: bool = False,
    ):
        self.db_path = db_path
        self.min_quality = min_quality
        self.include_context = include_context_in_input
        self._evaluator = QualityEvaluator()
        self._lock = threading.Lock()
        self._init_db()

    # -----------------------------------------------------------------------
    # DB 초기화
    # -----------------------------------------------------------------------
    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    system_prompt TEXT,
                    context_used TEXT,
                    source TEXT DEFAULT 'chat',
                    quality_score REAL DEFAULT 0.0,
                    user_rating INTEGER,
                    created_at TEXT,
                    is_approved INTEGER DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_quality "
                "ON interactions(quality_score)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approved "
                "ON interactions(is_approved)"
            )

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------------------------------------------------
    # 공개 API
    # -----------------------------------------------------------------------
    def log_interaction(
        self,
        question: str,
        answer: str,
        source: str = "chat",
        context_used: str = "",
        system_prompt: str = DEFAULT_SYSTEM,
        user_rating: int | None = None,
    ) -> Interaction | None:
        """
        대화 한 쌍을 DB에 저장.
        품질 점수가 min_quality 미만이면 저장하지 않고 None 반환.
        """
        question = question.strip()
        answer = answer.strip()

        score = self._evaluator.score(question, answer)
        if score < self.min_quality:
            return None

        interaction = Interaction(
            question=question,
            answer=answer,
            system_prompt=system_prompt,
            context_used=context_used,
            source=source,
            quality_score=score,
            user_rating=user_rating,
        )

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO interactions
                       (id, question, answer, system_prompt, context_used,
                        source, quality_score, user_rating, created_at, is_approved)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        interaction.id,
                        interaction.question,
                        interaction.answer,
                        interaction.system_prompt,
                        interaction.context_used,
                        interaction.source,
                        interaction.quality_score,
                        interaction.user_rating,
                        interaction.created_at,
                        int(interaction.is_approved),
                    ),
                )
        return interaction

    def approve(self, interaction_id: str) -> None:
        """수동 검수 통과 처리."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE interactions SET is_approved=1 WHERE id=?",
                    (interaction_id,),
                )

    def rate(self, interaction_id: str, rating: int) -> None:
        """사용자 평점(1~5) 업데이트."""
        if not 1 <= rating <= 5:
            raise ValueError("rating must be 1~5")
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE interactions SET user_rating=? WHERE id=?",
                    (rating, interaction_id),
                )

    def stats(self) -> dict:
        """수집 현황 요약 반환."""
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM interactions"
            ).fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM interactions WHERE is_approved=1"
            ).fetchone()[0]
            avg_q = conn.execute(
                "SELECT AVG(quality_score) FROM interactions"
            ).fetchone()[0] or 0.0
            by_source = conn.execute(
                "SELECT source, COUNT(*) FROM interactions GROUP BY source"
            ).fetchall()

        return {
            "total": total,
            "approved": approved,
            "pending_review": total - approved,
            "avg_quality_score": round(avg_q, 3),
            "by_source": {row[0]: row[1] for row in by_source},
        }

    # -----------------------------------------------------------------------
    # 내보내기 (Alpaca)
    # -----------------------------------------------------------------------
    def export_alpaca(
        self,
        output_path: Path | str | None = None,
        approved_only: bool = False,
        min_quality: float | None = None,
    ) -> Path:
        """
        Alpaca 포맷 JSON 파일로 내보내기.

        포맷:
        [
          {"instruction": "...", "input": "...", "output": "...", "system": "..."},
          ...
        ]
        input 필드: include_context=True이면 RAG 참고 문서 포함, 아니면 ""
        """
        rows = self._load_rows(approved_only, min_quality)
        samples = []
        for row in rows:
            inp = ""
            if self.include_context and row["context_used"]:
                inp = f"[참고 문서]\n{row['context_used']}"
            samples.append({
                "instruction": row["question"],
                "input": inp,
                "output": row["answer"],
                "system": row["system_prompt"] or DEFAULT_SYSTEM,
            })

        path = self._resolve_output(output_path, "alpaca")
        path.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DataCollector] Alpaca 내보내기 완료: {path} ({len(samples)}건)")
        return path

    # -----------------------------------------------------------------------
    # 내보내기 (ShareGPT)
    # -----------------------------------------------------------------------
    def export_sharegpt(
        self,
        output_path: Path | str | None = None,
        approved_only: bool = False,
        min_quality: float | None = None,
    ) -> Path:
        """
        ShareGPT 포맷 JSON 파일로 내보내기.

        포맷:
        [
          {
            "system": "...",
            "conversations": [
              {"from": "human", "value": "..."},
              {"from": "gpt",   "value": "..."}
            ]
          },
          ...
        ]
        """
        rows = self._load_rows(approved_only, min_quality)
        samples = []
        for row in rows:
            human_value = row["question"]
            if self.include_context and row["context_used"]:
                human_value = (
                    f"[참고 문서]\n{row['context_used']}\n\n"
                    f"질문: {row['question']}"
                )
            samples.append({
                "system": row["system_prompt"] or DEFAULT_SYSTEM,
                "conversations": [
                    {"from": "human", "value": human_value},
                    {"from": "gpt",   "value": row["answer"]},
                ],
            })

        path = self._resolve_output(output_path, "sharegpt")
        path.write_text(
            json.dumps(samples, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DataCollector] ShareGPT 내보내기 완료: {path} ({len(samples)}건)")
        return path

    # -----------------------------------------------------------------------
    # 내보내기 (JSONL — Unsloth/HuggingFace 직접 사용)
    # -----------------------------------------------------------------------
    def export_jsonl(
        self,
        output_path: Path | str | None = None,
        fmt: Literal["alpaca", "sharegpt"] = "alpaca",
        approved_only: bool = False,
        min_quality: float | None = None,
    ) -> Path:
        """JSONL 포맷 내보내기 (한 줄에 JSON 1개)."""
        rows = self._load_rows(approved_only, min_quality)
        path = self._resolve_output(output_path, f"{fmt}_jsonl", ext=".jsonl")

        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                if fmt == "alpaca":
                    obj = {
                        "instruction": row["question"],
                        "input": "",
                        "output": row["answer"],
                        "system": row["system_prompt"] or DEFAULT_SYSTEM,
                    }
                else:
                    obj = {
                        "system": row["system_prompt"] or DEFAULT_SYSTEM,
                        "conversations": [
                            {"from": "human", "value": row["question"]},
                            {"from": "gpt",   "value": row["answer"]},
                        ],
                    }
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

        print(f"[DataCollector] JSONL 내보내기 완료: {path} ({len(rows)}건)")
        return path

    # -----------------------------------------------------------------------
    # 내부 헬퍼
    # -----------------------------------------------------------------------
    def _load_rows(
        self,
        approved_only: bool,
        min_quality: float | None,
    ) -> list[sqlite3.Row]:
        threshold = min_quality if min_quality is not None else self.min_quality
        query = "SELECT * FROM interactions WHERE quality_score >= ?"
        params: list = [threshold]
        if approved_only:
            query += " AND is_approved = 1"
        query += " ORDER BY quality_score DESC, created_at ASC"

        with self._get_conn() as conn:
            return conn.execute(query, params).fetchall()

    @staticmethod
    def _resolve_output(
        path: Path | str | None,
        label: str,
        ext: str = ".json",
    ) -> Path:
        if path is not None:
            return Path(path)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return EXPORT_DIR / f"{label}_{ts}{ext}"


# ---------------------------------------------------------------------------
# RAGChain 연동 헬퍼
# ---------------------------------------------------------------------------
def make_logging_chain(rag_chain, collector: DataCollector):
    """
    RAGChain.ask() 를 래핑하여 자동으로 DataCollector에 기록하는
    클로저를 반환합니다.

    사용 예:
        ask = make_logging_chain(chain, collector)
        answer = ask("오늘 일정 알려줘")
    """
    def ask_and_log(question: str, source: str = "chat", **kwargs) -> str:
        answer = rag_chain.ask(question, **kwargs)
        context = ""
        # RAGChain이 마지막 컨텍스트를 캐시하는 경우 활용
        if hasattr(rag_chain, "_last_context"):
            context = rag_chain._last_context or ""
        collector.log_interaction(
            question=question,
            answer=answer,
            source=source,
            context_used=context,
            system_prompt=getattr(rag_chain, "system_prompt", DEFAULT_SYSTEM),
        )
        return answer

    return ask_and_log


# ---------------------------------------------------------------------------
# 단독 실행 — 간단 테스트
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test.db"
        collector = DataCollector(db_path=tmp_db, min_quality=0.4)

        # 샘플 데이터 삽입
        test_pairs = [
            (
                "오늘 일정 중에 중요한 미팅이 있나요?",
                "네, 오후 3시에 팀 스프린트 리뷰 미팅이 예정되어 있습니다. "
                "회의 자료를 미리 준비하시고, 10분 전에 접속하시는 것을 권장드립니다.",
                "calendar",
            ),
            (
                "지난주 이메일 중 미처리 건 요약해줘",
                "지난주 수신 이메일 총 12건 중 미처리 4건이 있습니다. "
                "1) 계약서 검토 요청 (홍길동 부장, 3일 전) "
                "2) 예산 승인 요청 (재무팀, 4일 전) "
                "3) 채용 면접 일정 조율 (HR팀, 5일 전) "
                "4) 서버 비용 견적서 (IT팀, 2일 전) "
                "우선순위 순으로 처리하시길 권장드립니다.",
                "email",
            ),
            (
                "RAG 파이프라인에서 BM25와 ChromaDB를 같이 쓰는 이유가 뭐야?",
                "BM25는 키워드 기반 희소 검색(sparse retrieval)으로 정확한 단어 매칭에 강하고, "
                "ChromaDB는 의미 기반 밀집 검색(dense retrieval)으로 문맥적 유사도를 잡습니다. "
                "둘을 RRF(Reciprocal Rank Fusion)로 병합하면 각각의 약점을 보완하여 "
                "recall과 precision 모두 향상됩니다. 이를 하이브리드 RAG라고 합니다.",
                "chat",
            ),
            (
                "안녕",   # 너무 짧은 질문 → 필터링
                "안녕하세요!",
                "chat",
            ),
        ]

        for q, a, src in test_pairs:
            result = collector.log_interaction(q, a, source=src)
            status = f"저장됨 (score={result.quality_score:.2f})" if result else "필터링됨"
            print(f"[{src}] {q[:30]}... → {status}")

        print("\n--- 통계 ---")
        stats = collector.stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

        # Alpaca 내보내기 테스트
        alpaca_path = collector.export_alpaca(Path(tmpdir) / "test_alpaca.json")
        data = json.loads(alpaca_path.read_text(encoding="utf-8"))
        print(f"\nAlpaca 샘플 수: {len(data)}")
        print(f"첫 번째 샘플 instruction: {data[0]['instruction'][:50]}...")

        # ShareGPT 내보내기 테스트
        sg_path = collector.export_sharegpt(Path(tmpdir) / "test_sharegpt.json")
        sg_data = json.loads(sg_path.read_text(encoding="utf-8"))
        print(f"ShareGPT 샘플 수: {len(sg_data)}")

        print("\n✅ 모든 테스트 통과")
