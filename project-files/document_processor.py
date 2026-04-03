"""
document_processor.py — 문서 청크 분할 및 전처리
--------------------------------------------------
RAGPipeline에 넣기 전 문서를 처리하는 모듈.

기능:
  - RecursiveCharacterTextSplitter 스타일 청크 분할
  - 한국어 / 영어 혼합 문서 처리
  - 메타데이터 자동 주입 (source, chunk_index, chunk_total 등)
  - 노이즈 제거 (공백 정규화, 특수문자 처리)

사용법:
    from document_processor import DocumentProcessor

    proc = DocumentProcessor(chunk_size=500, chunk_overlap=50)
    chunks = proc.process("긴 문서 내용...", source="파일명.txt")
    # chunks: [{"text": ..., "metadata": {...}}, ...]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterator

logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────
DEFAULT_CHUNK_SIZE    = 500    # 청크 최대 글자 수
DEFAULT_CHUNK_OVERLAP = 50     # 청크 간 오버랩 글자 수
MIN_CHUNK_SIZE        = 50     # 이 길이 미만 청크는 버림

# 분할 우선순위 구분자 (앞에서부터 우선 시도)
_SEPARATORS = [
    "\n\n",   # 단락
    "\n",     # 줄바꿈
    ". ",     # 문장 (영어)
    "。",     # 문장 (한국어/일본어)
    "! ",
    "? ",
    "!",
    "?",
    " ",      # 단어
    "",       # 글자 (최후 수단)
]


# ── 데이터 클래스 ─────────────────────────────────────────────
@dataclass
class Chunk:
    text:     str
    metadata: dict = field(default_factory=dict)


# ════════════════════════════════════════════════════════════
#  핵심: RecursiveCharacterSplitter
# ════════════════════════════════════════════════════════════
class RecursiveCharacterSplitter:
    """
    LangChain RecursiveCharacterTextSplitter 동작을 직접 구현.
    sentence-transformers 토큰 기반이 아닌 '글자 수' 기반으로
    한국어처럼 토큰 수 예측이 어려운 언어에서도 안정적으로 동작.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        separators: list[str] | None = None,
        keep_separator: bool = True,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap({chunk_overlap}) >= chunk_size({chunk_size})"
            )
        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators    = separators or _SEPARATORS
        self.keep_separator = keep_separator

    def split(self, text: str) -> list[str]:
        """텍스트를 청크 리스트로 분할"""
        if not text.strip():
            return []
        chunks = list(self._split_recursive(text, self.separators))
        merged = self._merge_chunks(chunks)
        return [c for c in merged if len(c.strip()) >= MIN_CHUNK_SIZE]

    # ── 내부 ─────────────────────────────────────────────────

    def _split_recursive(self, text: str, separators: list[str]) -> Iterator[str]:
        """재귀적으로 구분자를 줄여가며 분할"""
        if len(text) <= self.chunk_size:
            yield text
            return

        sep = separators[0] if separators else ""
        remaining_seps = separators[1:] if len(separators) > 1 else []

        if sep == "":
            # 글자 단위 강제 분할
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                yield text[i:i + self.chunk_size]
            return

        parts = text.split(sep)
        for part in parts:
            part = (part + sep) if self.keep_separator and sep.strip() else part
            if not part.strip():
                continue
            if len(part) <= self.chunk_size:
                yield part
            else:
                yield from self._split_recursive(part, remaining_seps)

    def _merge_chunks(self, pieces: list[str]) -> list[str]:
        """
        작은 조각들을 chunk_size 이하로 합치되,
        chunk_overlap 만큼 앞 내용을 이월.
        """
        merged: list[str] = []
        current = ""
        overlap_buf = ""

        for piece in pieces:
            # candidate: overlap_buf 를 앞에 붙인 실제 병합 후보
            candidate = (overlap_buf + piece).strip()

            if len(current) + len(candidate) <= self.chunk_size:
                current += candidate   # 오버랩 포함 조각을 현재 청크에 추가
            else:
                if current.strip():
                    merged.append(current.strip())
                # 오버랩: 현재 청크 끝부분을 다음 청크에 이월
                overlap_buf = current[-self.chunk_overlap:] if self.chunk_overlap else ""
                current = overlap_buf + piece

        if current.strip():
            merged.append(current.strip())

        return merged


# ════════════════════════════════════════════════════════════
#  전처리 유틸
# ════════════════════════════════════════════════════════════
def clean_text(text: str) -> str:
    """
    기본 노이즈 제거:
    - 연속 공백 → 단일 공백
    - 3개 이상 줄바꿈 → 2개
    - 제어 문자 제거 (탭은 공백으로)
    - 문장 앞뒤 공백 정리
    """
    # 탭 → 공백
    text = text.replace("\t", " ")
    # 제어 문자 제거 (줄바꿈·공백 제외)
    text = re.sub(r"[^\S\n ]", " ", text)
    # 연속 공백 → 단일
    text = re.sub(r" {2,}", " ", text)
    # 3개 이상 줄바꿈 → 2개
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metadata(
    text: str,
    source: str = "",
    chunk_index: int = 0,
    chunk_total: int = 1,
    extra: dict | None = None,
) -> dict:
    """청크 메타데이터 생성"""
    meta = {
        "source":      source,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "char_count":  len(text),
        # 언어 힌트 (한국어 포함 여부)
        "lang": "ko" if re.search(r"[가-힣]", text) else "en",
    }
    if extra:
        meta.update(extra)
    return meta


# ════════════════════════════════════════════════════════════
#  DocumentProcessor — 통합 인터페이스
# ════════════════════════════════════════════════════════════
class DocumentProcessor:
    """
    문서 → 청크 리스트 변환.

    사용 예:
        proc = DocumentProcessor(chunk_size=500, chunk_overlap=50)

        # 단일 문서
        chunks = proc.process(text, source="report.txt")

        # 여러 문서 배치
        all_chunks = proc.process_batch(
            texts=["문서1", "문서2"],
            sources=["a.txt", "b.txt"],
        )

        # RAGPipeline 직접 주입
        texts, metas, ids = proc.to_rag_inputs(chunks)
        rag.add_documents(texts, metas, ids)
    """

    def __init__(
        self,
        chunk_size: int    = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        clean: bool        = True,
    ) -> None:
        self.splitter = RecursiveCharacterSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.clean = clean
        logger.info(
            "DocumentProcessor 초기화 — chunk_size=%d, overlap=%d",
            chunk_size, chunk_overlap,
        )

    def process(
        self,
        text: str,
        source: str = "",
        extra_meta: dict | None = None,
    ) -> list[Chunk]:
        """단일 문서를 청크 리스트로 변환"""
        if self.clean:
            text = clean_text(text)

        raw_chunks = self.splitter.split(text)
        total = len(raw_chunks)

        result: list[Chunk] = []
        for i, chunk_text in enumerate(raw_chunks):
            meta = extract_metadata(
                chunk_text,
                source=source,
                chunk_index=i,
                chunk_total=total,
                extra=extra_meta,
            )
            result.append(Chunk(text=chunk_text, metadata=meta))

        logger.debug("'%s' → %d 청크", source or "unnamed", total)
        return result

    def process_batch(
        self,
        texts: list[str],
        sources: list[str] | None = None,
        extra_metas: list[dict] | None = None,
    ) -> list[Chunk]:
        """여러 문서 배치 처리"""
        _sources = sources or [""] * len(texts)
        _metas   = extra_metas or [{}] * len(texts)

        all_chunks: list[Chunk] = []
        for text, src, meta in zip(texts, _sources, _metas):
            all_chunks.extend(self.process(text, source=src, extra_meta=meta))

        logger.info("배치 처리 완료 — 문서 %d개 → 청크 %d개", len(texts), len(all_chunks))
        return all_chunks

    @staticmethod
    def to_rag_inputs(
        chunks: list[Chunk],
        id_prefix: str = "chunk",
    ) -> tuple[list[str], list[dict], list[str]]:
        """
        RAGPipeline.add_documents() 에 바로 전달 가능한 형태로 변환.

        반환: (texts, metadatas, ids)
        """
        texts = [c.text for c in chunks]
        metas = [c.metadata for c in chunks]
        ids   = [
            f"{id_prefix}_{m['source']}_{m['chunk_index']}"
            .replace(" ", "_").replace("/", "-").replace("\\", "-")
            for m in metas
        ]
        return texts, metas, ids


# ── CLI 테스트 ───────────────────────────────────────────────
if __name__ == "__main__":
    sample = """
    PlanQuest는 완전 로컬 실행 AI 개인 비서 프로젝트입니다.
    Ollama와 Qwen2.5를 기반으로 동작하며, 인터넷 연결 없이 사용할 수 있습니다.

    RAG 파이프라인은 ChromaDB(밀집)와 BM25(희소) 검색을 결합한 하이브리드 방식을 사용합니다.
    RRF(Reciprocal Rank Fusion) 알고리즘으로 두 검색 결과를 병합하고,
    bge-reranker로 최종 순위를 재조정합니다.

    보안 측면에서는 SQLCipher AES-256 암호화를 사용하고,
    keyring으로 토큰을 안전하게 저장합니다.
    Google Calendar와 Gmail API 연동도 지원합니다.
    """ * 3  # 반복해서 긴 문서 시뮬레이션

    print("\n" + "═" * 55)
    print("  DocumentProcessor 테스트")
    print("═" * 55)
    print(f"  입력 길이: {len(sample)} 글자\n")

    proc = DocumentProcessor(chunk_size=200, chunk_overlap=30)
    chunks = proc.process(sample, source="test_doc.txt")

    print(f"  총 청크 수: {len(chunks)}")
    print("─" * 55)
    for c in chunks:
        m = c.metadata
        print(
            f"  [{m['chunk_index']:02d}/{m['chunk_total']-1:02d}] "
            f"{m['char_count']}자 | lang={m['lang']} | "
            f"{c.text[:60].strip()}..."
        )

    texts, metas, ids = DocumentProcessor.to_rag_inputs(chunks)
    print(f"\n  RAG 입력 준비: {len(texts)}개")
    print(f"  ID 예시: {ids[0]}")
    print("\n✅ 테스트 완료")
