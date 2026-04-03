"""
rrf_tuner.py — RRF k 파라미터 튜닝 실험 유틸리티
-------------------------------------------------
정답 셋(ground truth)을 기준으로 여러 k 값을 실험하여
최적 RRF k 값을 찾아줍니다.

평가 지표:
  - MRR@K  (Mean Reciprocal Rank)
  - Recall@K
  - NDCG@K  (Normalized Discounted Cumulative Gain)

사용법:
    from rrf_tuner import RRFTuner

    tuner = RRFTuner(rag_pipeline)
    tuner.add_ground_truth([
        {"query": "Ollama란?", "relevant_ids": ["doc_0", "doc_1"]},
        ...
    ])
    report = tuner.run(k_values=[10, 30, 60, 100], top_k=5)
    print(report)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── 평가 데이터 클래스 ────────────────────────────────────────
@dataclass
class QueryGT:
    """단일 쿼리의 정답(ground truth)"""
    query:        str
    relevant_ids: list[str]          # 정답 문서 id 목록
    extra:        dict = field(default_factory=dict)


@dataclass
class EvalResult:
    """단일 k 값에 대한 평가 결과"""
    k:       int
    mrr:     float
    recall:  float
    ndcg:    float
    details: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"k={self.k:4d} | "
            f"MRR@K={self.mrr:.4f} | "
            f"Recall@K={self.recall:.4f} | "
            f"NDCG@K={self.ndcg:.4f}"
        )


# ── 평가 지표 계산 ────────────────────────────────────────────
def _mrr_at_k(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """MRR: 첫 번째 정답이 몇 번째에 등장하는지"""
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def _recall_at_k(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Recall: 정답 중 검색된 비율"""
    if not relevant_ids:
        return 0.0
    hits = sum(1 for doc_id in retrieved_ids if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def _ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """NDCG: 상위 랭크 정답에 더 높은 가중치"""
    def dcg(ids: list[str]) -> float:
        return sum(
            1.0 / math.log2(rank + 1)
            for rank, doc_id in enumerate(ids, start=1)
            if doc_id in relevant_ids
        )

    actual_dcg = dcg(retrieved_ids)
    # ideal DCG: 정답 문서를 1위부터 순서대로 놓은 경우
    # retrieved_ids 길이만큼 자른 ideal 리스트 사용
    ideal_count = min(len(relevant_ids), len(retrieved_ids))
    ideal_dcg   = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_count + 1)
    )
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


# ── RRF 재실행 (k 값 주입용 독립 함수) ───────────────────────
def rrf_with_k(
    result_lists: list[list[dict]],
    k: int,
    top_k: int,
) -> list[str]:
    """
    주어진 k 로 RRF 재계산 후 상위 top_k의 id 리스트 반환.
    (실제 retriever 재호출 없이 기존 결과 재활용)
    """
    scores: dict[str, float] = {}
    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    ranked = sorted(scores, key=lambda x: scores[x], reverse=True)
    return ranked[:top_k]


# ════════════════════════════════════════════════════════════
#  RRFTuner
# ════════════════════════════════════════════════════════════
class RRFTuner:
    """
    RAGPipeline 위에서 RRF k 파라미터를 자동 튜닝.

    동작 방식:
    1. 각 쿼리에 대해 dense/sparse retriever를 한 번씩만 호출
    2. 결과를 캐시해두고 k 값만 바꿔가며 RRF 재계산
    3. MRR, Recall, NDCG 기준으로 최적 k 선택
    """

    def __init__(self, rag_pipeline: Any) -> None:
        self._rag   = rag_pipeline
        self._gts:  list[QueryGT] = []

    def add_ground_truth(self, items: list[dict]) -> None:
        """
        정답 데이터 추가.
        items 형식: [{"query": "...", "relevant_ids": ["id1", ...]}, ...]
        """
        for item in items:
            self._gts.append(QueryGT(
                query=item["query"],
                relevant_ids=item["relevant_ids"],
                extra=item.get("extra", {}),
            ))
        logger.info("GT %d개 등록 (총 %d개)", len(items), len(self._gts))

    def run(
        self,
        k_values: list[int] | None = None,
        top_k: int = 5,
        candidate: int = 20,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        여러 k 값에 대한 평가 실행.

        반환:
        {
            "best_k":    int,
            "results":   [EvalResult, ...],
            "summary":   str,
        }
        """
        _k_values = k_values or [10, 30, 60, 100, 150]

        if not self._gts:
            raise ValueError("ground truth 데이터가 없습니다. add_ground_truth() 를 먼저 호출하세요.")

        # 1) 각 쿼리에 대해 retriever 결과 사전 수집 (k 무관)
        cached: list[tuple[list[dict], list[dict], set[str]]] = []
        for gt in self._gts:
            dense_res  = self._rag.dense.search(gt.query,  top_k=candidate)
            sparse_res = self._rag.sparse.search(gt.query, top_k=candidate)
            cached.append((dense_res, sparse_res, set(gt.relevant_ids)))

        # 2) k 값별 평가
        eval_results: list[EvalResult] = []

        for k in _k_values:
            mrr_scores, recall_scores, ndcg_scores = [], [], []
            details = []

            for (dense_res, sparse_res, relevant_ids), gt in zip(cached, self._gts):
                retrieved_ids = rrf_with_k([dense_res, sparse_res], k=k, top_k=top_k)

                mrr    = _mrr_at_k(retrieved_ids, relevant_ids)
                recall = _recall_at_k(retrieved_ids, relevant_ids)
                ndcg   = _ndcg_at_k(retrieved_ids, relevant_ids)

                mrr_scores.append(mrr)
                recall_scores.append(recall)
                ndcg_scores.append(ndcg)
                details.append({
                    "query":         gt.query,
                    "retrieved_ids": retrieved_ids,
                    "relevant_ids":  list(relevant_ids),
                    "mrr":           round(mrr, 4),
                    "recall":        round(recall, 4),
                    "ndcg":          round(ndcg, 4),
                })

            result = EvalResult(
                k=k,
                mrr=round(sum(mrr_scores) / len(mrr_scores), 4),
                recall=round(sum(recall_scores) / len(recall_scores), 4),
                ndcg=round(sum(ndcg_scores) / len(ndcg_scores), 4),
                details=details,
            )
            eval_results.append(result)

            if verbose:
                print(f"  {result}")

        # 3) 최적 k 선택 (NDCG 기준)
        best = max(eval_results, key=lambda r: r.ndcg)

        summary = self._build_summary(eval_results, best, top_k)
        if verbose:
            print("\n" + summary)

        return {
            "best_k":   best.k,
            "results":  eval_results,
            "summary":  summary,
        }

    @staticmethod
    def _build_summary(
        results: list[EvalResult],
        best: EvalResult,
        top_k: int,
    ) -> str:
        lines = [
            "═" * 55,
            f"  RRF 튜닝 결과 (top_k={top_k})",
            "═" * 55,
            f"  {'k':>6} | {'MRR@K':>8} | {'Recall@K':>10} | {'NDCG@K':>8}",
            "─" * 55,
        ]
        for r in results:
            marker = " ★" if r.k == best.k else ""
            lines.append(
                f"  {r.k:>6} | {r.mrr:>8.4f} | {r.recall:>10.4f} | {r.ndcg:>8.4f}{marker}"
            )
        lines += [
            "─" * 55,
            f"  최적 k = {best.k}  (NDCG={best.ndcg:.4f})",
            "═" * 55,
        ]
        return "\n".join(lines)


# ── CLI 테스트 ───────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os

    # rag_pipeline 경로 추가 (향후 통합 테스트 시 사용)
    sys.path.insert(0, os.path.dirname(__file__))

    print("\n" + "═" * 55)
    print("  RRFTuner 단독 테스트 (BM25만 사용)")
    print("═" * 55)

    # 평가 지표 단위 테스트
    print("\n[평가 지표 검증]")
    retrieved = ["doc_0", "doc_2", "doc_4", "doc_1", "doc_3"]
    relevant  = {"doc_0", "doc_1"}

    mrr = _mrr_at_k(retrieved, relevant)
    rec = _recall_at_k(retrieved, relevant)
    ndcg = _ndcg_at_k(retrieved, relevant)

    print(f"  MRR    = {mrr:.4f}  (예상: 1.0 — doc_0이 rank 1)")
    print(f"  Recall = {rec:.4f}  (예상: 1.0 — doc_0, doc_1 모두 포함)")
    print(f"  NDCG   = {ndcg:.4f}")

    assert mrr == 1.0,   f"MRR 오류: {mrr}"
    assert rec == 1.0,   f"Recall 오류: {rec}"
    assert 0 < ndcg <= 1, f"NDCG 범위 오류: {ndcg}"
    print("  ✅ 평가 지표 정확")

    print("\n[rrf_with_k 검증]")
    list_a = [{"id": "doc_0", "score": 1.0}, {"id": "doc_1", "score": 0.8}]
    list_b = [{"id": "doc_1", "score": 1.0}, {"id": "doc_2", "score": 0.6}]
    ids_k60  = rrf_with_k([list_a, list_b], k=60,  top_k=3)
    ids_k10  = rrf_with_k([list_a, list_b], k=10,  top_k=3)
    assert ids_k60[0] == "doc_1", "doc_1(두 리스트 공통)이 1위여야 함"
    assert ids_k10[0] == "doc_1"
    print(f"  k=60 순서: {ids_k60}")
    print(f"  k=10 순서: {ids_k10}")
    print("  ✅ rrf_with_k 정확")

    print("\n✅ 모든 테스트 통과")
