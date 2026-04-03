"""
rag_pipeline.py — RAG 파이프라인
---------------------------------
ChromaDB (밀집 벡터) + BM25 (희소 키워드) + RRF 병합 + bge-reranker

사용법:
    from rag_pipeline import RAGPipeline

    rag = RAGPipeline()
    rag.add_documents(["문서1 내용", "문서2 내용"], metadatas=[{...}, {...}])
    results = rag.query("질문", top_k=5)
    # results: [{"text": ..., "score": ..., "metadata": ...}, ...]
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── 의존 패키지 지연 임포트 (설치 안 된 경우 안내) ───────────
def _import_or_raise(pkg: str, import_name: str | None = None) -> Any:
    import importlib
    name = import_name or pkg
    try:
        return importlib.import_module(name)
    except ImportError:
        raise ImportError(
            f"'{pkg}' 패키지가 필요합니다. "
            f"pip install {pkg} 로 설치하세요."
        )

# ── 상수 ─────────────────────────────────────────────────────
DEFAULT_COLLECTION   = "planquest"
DEFAULT_EMBED_MODEL  = "BAAI/bge-m3"          # ChromaDB 임베딩
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
CHROMA_DIR           = "./chroma_db"
BM25_PATH            = "./bm25_index.pkl"
RRF_K                = 60                      # RRF 상수 (일반적으로 60)
DEFAULT_CANDIDATE    = 20                      # RRF 전 각 retriever 후보 수
EMBED_BATCH_SIZE     = 32                      # 임베딩 배치 크기
DEFAULT_TOP_K        = 5                       # 최종 반환 개수


# ════════════════════════════════════════════════════════════
#  1. 밀집 Retriever — ChromaDB
# ════════════════════════════════════════════════════════════
class DenseRetriever:
    """
    ChromaDB + sentence-transformers 임베딩 기반 밀집 벡터 검색.
    persist_directory에 영구 저장.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
        persist_dir: str = CHROMA_DIR,
    ) -> None:
        chromadb = _import_or_raise("chromadb")
        sentence_transformers = _import_or_raise(
            "sentence-transformers", "sentence_transformers"
        )

        self.embed_model_name = embed_model
        self._embedder = sentence_transformers.SentenceTransformer(embed_model)

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "DenseRetriever 초기화 — collection=%s, docs=%d",
            collection_name, self._col.count(),
        )

    def add(self, texts: list[str], metadatas: list[dict] | None = None, ids: list[str] | None = None) -> None:
        """
        문서 추가. 임베딩은 EMBED_BATCH_SIZE 단위 배치 처리.
        이미 존재하는 id는 upsert로 덮어씀.
        """
        if not texts:
            return

        _ids  = ids or [f"doc_{self._col.count() + i}" for i in range(len(texts))]
        # ChromaDB는 빈 dict 메타데이터를 거부함 → 기본값 보장
        _meta = [
            (m if m else {"_source": "unknown"})
            for m in (metadatas or [{} for _ in texts])
        ]

        # 배치 임베딩 (메모리 안정성)
        all_embeddings: list[list[float]] = []
        for batch_start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[batch_start:batch_start + EMBED_BATCH_SIZE]
            embs  = self._embedder.encode(
                batch,
                batch_size=EMBED_BATCH_SIZE,
                show_progress_bar=len(texts) > EMBED_BATCH_SIZE,
                normalize_embeddings=True,   # cosine 유사도용 L2 정규화
            ).tolist()
            all_embeddings.extend(embs)
            logger.debug(
                "임베딩 배치 %d~%d 완료",
                batch_start, batch_start + len(batch) - 1,
            )

        # upsert: 중복 id도 안전하게 처리
        self._col.upsert(
            ids=_ids,
            documents=texts,
            embeddings=all_embeddings,
            metadatas=_meta,
        )
        logger.info("DenseRetriever: %d개 문서 추가/갱신 (총 %d개)", len(texts), self._col.count())

    def search(self, query: str, top_k: int = DEFAULT_CANDIDATE) -> list[dict]:
        """
        코사인 유사도 기반 검색.
        반환: [{"id": ..., "text": ..., "score": ..., "metadata": ...}]
        """
        if self._col.count() == 0:
            return []

        q_emb = self._embedder.encode([query], show_progress_bar=False).tolist()
        results = self._col.query(
            query_embeddings=q_emb,
            n_results=min(top_k, self._col.count()),
            include=["documents", "distances", "metadatas"],
        )

        output = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # ChromaDB cosine distance → similarity (1 - distance)
            output.append({
                "id":       results["ids"][0][len(output)],
                "text":     doc,
                "score":    round(1.0 - dist, 6),
                "metadata": meta,
            })
        return output

    @property
    def doc_count(self) -> int:
        return self._col.count()


# ════════════════════════════════════════════════════════════
#  2. 희소 Retriever — BM25
# ════════════════════════════════════════════════════════════
class SparseRetriever:
    """
    rank_bm25(BM25Okapi) 기반 희소 키워드 검색.
    인덱스는 pickle로 영구 저장.
    """

    def __init__(self, index_path: str = BM25_PATH) -> None:
        self._index_path = Path(index_path)
        self._texts:     list[str]  = []
        self._metadatas: list[dict] = []
        self._ids:       list[str]  = []
        self._bm25 = None

        if self._index_path.exists():
            self._load()

    def add(self, texts: list[str], metadatas: list[dict] | None = None, ids: list[str] | None = None) -> None:
        if not texts:
            return
        base_id = len(self._texts)
        self._texts.extend(texts)
        self._metadatas.extend(metadatas or [{} for _ in texts])
        self._ids.extend(ids or [f"doc_{base_id + i}" for i in range(len(texts))])
        self._build_index()
        self._save()
        logger.info("SparseRetriever: %d개 문서 추가 (총 %d개)", len(texts), len(self._texts))

    def search(self, query: str, top_k: int = DEFAULT_CANDIDATE) -> list[dict]:
        """
        BM25 점수 기반 검색.
        반환: [{"id": ..., "text": ..., "score": ..., "metadata": ...}]
        """
        if not self._texts or self._bm25 is None:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # 점수 0 이상인 것만, 상위 top_k
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        output = []
        for idx, score in ranked:
            if score <= 0:
                continue
            output.append({
                "id":       self._ids[idx],
                "text":     self._texts[idx],
                "score":    round(float(score), 6),
                "metadata": self._metadatas[idx],
            })
        return output

    # ── 한국어 + 영어 토크나이저 ─────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        한국어/영어 혼합 BM25 토크나이저.

        전략:
        1. konlpy(Okt) 설치된 경우 → 형태소 분석 (명사+동사+형용사)
        2. 미설치 시 → 정규식 기반 한글 음절 단위 + 영어 단어 분리
           (konlpy는 JVM 의존이라 선택적 적용)
        """
        # konlpy Okt 시도
        try:
            import importlib
            konlpy = importlib.import_module("konlpy.tag")
            okt = konlpy.Okt()
            # 명사·동사·형용사·알파벳 추출
            tokens = okt.morphs(text, stem=True)
            return [t.lower() for t in tokens if len(t) > 1]
        except Exception:
            pass

        # fallback: 정규식 분리
        # 한글 2글자 이상 어절, 영어 단어
        tokens = re.findall(r"[가-힣]{2,}|[a-zA-Z0-9]{2,}", text)
        return [t.lower() for t in tokens]

    def _build_index(self) -> None:
        rank_bm25 = _import_or_raise("rank-bm25", "rank_bm25")
        tokenized = [self._tokenize(t) for t in self._texts]
        self._bm25 = rank_bm25.BM25Okapi(tokenized)

    # ── HMAC 서명 키 (환경변수 우선, 없으면 경고 후 기본값) ──────
    _HMAC_ENV = "PLANQUEST_BM25_HMAC_KEY"

    def _hmac_key(self) -> bytes:
        key = os.environ.get(self._HMAC_ENV, "")
        if not key:
            logger.warning(
                "환경변수 %s 가 설정되지 않았습니다. "
                "BM25 인덱스 무결성 검증에 기본 키를 사용합니다. "
                "프로덕션 환경에서는 반드시 설정하세요.",
                self._HMAC_ENV,
            )
            key = "planquest-default-hmac-key-change-in-prod"
        return key.encode()

    def _save(self) -> None:
        import hmac as _hmac
        data = {
            "texts":     self._texts,
            "metadatas": self._metadatas,
            "ids":       self._ids,
        }
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = pickle.dumps(data)
        # SHA-256 HMAC 서명 생성 → 별도 .sig 파일에 저장
        sig = _hmac.new(self._hmac_key(), payload, hashlib.sha256).hexdigest()
        sig_path = self._index_path.with_suffix(".sig")
        with open(self._index_path, "wb") as f:
            f.write(payload)
        sig_path.write_text(sig, encoding="utf-8")
        logger.debug("BM25 인덱스 저장 (HMAC 서명 포함): %s", self._index_path)

    def _load(self) -> None:
        import hmac as _hmac
        sig_path = self._index_path.with_suffix(".sig")
        payload = self._index_path.read_bytes()
        # 서명 파일 존재 시 무결성 검증
        if sig_path.exists():
            expected = sig_path.read_text(encoding="utf-8").strip()
            actual = _hmac.new(self._hmac_key(), payload, hashlib.sha256).hexdigest()
            if not _hmac.compare_digest(expected, actual):
                raise ValueError(
                    "BM25 인덱스 파일의 HMAC 서명 검증 실패. "
                    "파일이 변조되었을 수 있습니다."
                )
        else:
            logger.warning("BM25 서명 파일(%s)이 없습니다. 무결성 검증 생략.", sig_path)
        data = pickle.loads(payload)  # nosec B301 — HMAC 검증 후 안전
        self._texts     = data["texts"]
        self._metadatas = data["metadatas"]
        self._ids       = data["ids"]
        if self._texts:
            self._build_index()
        logger.info("BM25 인덱스 로드: %d개 문서", len(self._texts))

    @property
    def doc_count(self) -> int:
        return len(self._texts)


# ════════════════════════════════════════════════════════════
#  3. RRF 병합
# ════════════════════════════════════════════════════════════
def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    k: int = RRF_K,
) -> list[dict]:
    """
    Reciprocal Rank Fusion.

    result_lists: 각 retriever의 결과 리스트 (id 포함)
    반환: RRF 점수로 정렬된 중복 제거 리스트
    """
    rrf_scores: dict[str, float] = {}
    doc_map:    dict[str, dict]  = {}

    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            doc_map[doc_id] = doc  # 마지막 출처의 메타 사용

    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {**doc_map[doc_id], "rrf_score": round(score, 8)}
        for doc_id, score in merged
    ]


# ════════════════════════════════════════════════════════════
#  4. Reranker — bge-reranker
# ════════════════════════════════════════════════════════════
class Reranker:
    """
    BAAI/bge-reranker-v2-m3 기반 Cross-Encoder reranking.
    FlagEmbedding 또는 sentence-transformers CrossEncoder 사용.
    """

    def __init__(self, model_name: str = DEFAULT_RERANK_MODEL) -> None:
        self._model_name = model_name
        self._model = None
        self._backend: str = ""
        self._load_model()

    def _load_model(self) -> None:
        # FlagEmbedding 우선 (공식 bge 라이브러리)
        try:
            FlagReranker = _import_or_raise(
                "FlagEmbedding", "FlagEmbedding"
            ).FlagReranker
            self._model   = FlagReranker(self._model_name, use_fp16=True)
            self._backend = "FlagEmbedding"
        except ImportError:
            pass

        # fallback: sentence-transformers CrossEncoder
        if self._model is None:
            try:
                CrossEncoder = _import_or_raise(
                    "sentence-transformers", "sentence_transformers"
                ).CrossEncoder
                self._model   = CrossEncoder(self._model_name)
                self._backend = "CrossEncoder"
            except ImportError:
                pass

        if self._model is None:
            logger.warning(
                "Reranker 모델 로드 실패 — FlagEmbedding 또는 "
                "sentence-transformers 설치 필요. rerank 스킵됨."
            )
        else:
            logger.info("Reranker 로드 완료 — backend=%s", self._backend)

    def rerank(
        self, query: str, docs: list[dict], top_k: int = DEFAULT_TOP_K
    ) -> list[dict]:
        """
        query-doc 쌍으로 점수 재계산 후 상위 top_k 반환.
        모델 로드 실패 시 입력 그대로 상위 top_k 반환.
        """
        if not docs:
            return []

        if self._model is None:
            logger.warning("Reranker 없음 — RRF 결과 그대로 사용")
            return docs[:top_k]

        pairs = [[query, doc["text"]] for doc in docs]

        if self._backend == "FlagEmbedding":
            scores = self._model.compute_score(pairs, normalize=True)
        else:
            scores = self._model.predict(pairs).tolist()

        for doc, score in zip(docs, scores):
            doc["rerank_score"] = round(float(score), 6)

        reranked = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)
        logger.debug("Reranker 완료 — 상위 %d개 반환", top_k)
        return reranked[:top_k]


# ════════════════════════════════════════════════════════════
#  5. RAGPipeline — 통합 인터페이스
# ════════════════════════════════════════════════════════════
class RAGPipeline:
    """
    DenseRetriever + SparseRetriever + RRF + Reranker 통합 파이프라인.

    사용 예:
        rag = RAGPipeline()
        rag.add_documents(texts, metadatas)
        results = rag.query("질문", top_k=5)
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model:     str = DEFAULT_EMBED_MODEL,
        rerank_model:    str = DEFAULT_RERANK_MODEL,
        persist_dir:     str = CHROMA_DIR,
        bm25_path:       str = BM25_PATH,
        use_reranker:    bool = True,
        rrf_candidate:   int = DEFAULT_CANDIDATE,
    ) -> None:
        logger.info("RAGPipeline 초기화 중...")
        self.dense    = DenseRetriever(collection_name, embed_model, persist_dir)
        self.sparse   = SparseRetriever(bm25_path)
        self.reranker = Reranker(rerank_model) if use_reranker else None
        self._rrf_candidate = rrf_candidate
        logger.info(
            "RAGPipeline 준비 완료 — dense=%d docs, sparse=%d docs",
            self.dense.doc_count, self.sparse.doc_count,
        )

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """
        Dense + Sparse 양쪽에 동일 문서 추가.
        ids는 두 retriever에서 공유 — RRF 병합의 핵심.
        """
        if not texts:
            logger.warning("add_documents: 빈 텍스트 리스트")
            return

        # 공유 id 생성
        base = self.dense.doc_count
        _ids = ids or [f"doc_{base + i}" for i in range(len(texts))]
        _meta = metadatas or [{} for _ in texts]

        self.dense.add(texts, _meta, _ids)
        self.sparse.add(texts, _meta, _ids)
        logger.info("문서 %d개 추가 완료", len(texts))

    def query(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        use_reranker: bool = True,
    ) -> list[dict]:
        """
        질의 실행 → RRF 병합 → (선택) rerank → 상위 top_k 반환.

        반환 스키마:
        [
            {
                "id":           str,
                "text":         str,
                "score":        float,   # 원래 retriever 점수
                "rrf_score":    float,   # RRF 병합 점수
                "rerank_score": float,   # reranker 점수 (use_reranker=True 시)
                "metadata":     dict,
            },
            ...
        ]
        """
        if not query.strip():
            return []

        logger.info("RAG 쿼리: '%s'", query[:60])

        # 1) 각 retriever 검색
        dense_results  = self.dense.search(query,  top_k=self._rrf_candidate)
        sparse_results = self.sparse.search(query, top_k=self._rrf_candidate)

        logger.debug(
            "dense=%d, sparse=%d 후보", len(dense_results), len(sparse_results)
        )

        # 2) RRF 병합
        fused = reciprocal_rank_fusion([dense_results, sparse_results])

        # 3) Rerank (요청 시 + 모델 로드된 경우)
        if use_reranker and self.reranker:
            final = self.reranker.rerank(query, fused, top_k=top_k)
        else:
            final = fused[:top_k]

        logger.info("RAG 완료 — %d개 결과 반환", len(final))
        return final

    def query_texts(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[str]:
        """텍스트만 반환하는 간편 메서드"""
        return [r["text"] for r in self.query(query, top_k=top_k)]

    @property
    def doc_count(self) -> int:
        return self.dense.doc_count


# ── 간단 CLI 테스트 ───────────────────────────────────────────
if __name__ == "__main__":
    import tempfile, shutil

    print("\n" + "═" * 55)
    print("  RAGPipeline 동작 테스트 (임시 디렉토리)")
    print("═" * 55 + "\n")

    tmp = tempfile.mkdtemp()
    try:
        rag = RAGPipeline(
            persist_dir=os.path.join(tmp, "chroma"),
            bm25_path=os.path.join(tmp, "bm25.pkl"),
            use_reranker=False,   # 빠른 테스트용
        )

        docs = [
            "Ollama는 로컬에서 LLM을 실행하는 도구입니다.",
            "ChromaDB는 벡터 데이터베이스입니다.",
            "BM25는 키워드 기반 검색 알고리즘입니다.",
            "RRF는 여러 검색 결과를 병합하는 방법입니다.",
            "PlanQuest는 AI 개인 비서 프로젝트입니다.",
        ]
        rag.add_documents(docs)
        print(f"문서 {rag.doc_count}개 추가 완료\n")

        results = rag.query("벡터 검색 도구", top_k=3, use_reranker=False)
        print("쿼리: '벡터 검색 도구'")
        print("─" * 40)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [rrf={r['rrf_score']:.6f}] {r['text']}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n✅ 테스트 완료")
