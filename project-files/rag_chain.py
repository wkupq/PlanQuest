"""
rag_chain.py — LangChain RAG 체인 (RAGPipeline + OllamaManager 연결)
----------------------------------------------------------------------
RAGPipeline으로 컨텍스트를 검색하고,
OllamaManager의 InferenceQueue를 통해 Qwen2.5에게 답변을 요청합니다.

사용법:
    from rag_chain import RAGChain

    chain = RAGChain()
    chain.rag.add_documents(["문서1", "문서2"])

    # 동기 호출
    answer = chain.ask("질문")

    # 비동기 (Future)
    future = chain.ask_async("질문", priority=0)
    answer = future.result(timeout=120)
"""

from __future__ import annotations

import logging
from concurrent.futures import Future
from string import Template
from ollama_manager import OllamaManager, get_manager
from rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── 기본 프롬프트 템플릿 ─────────────────────────────────────
# $context, $question 두 변수를 사용
_DEFAULT_SYSTEM = "당신은 사용자의 개인 비서 AI입니다. 주어진 컨텍스트를 바탕으로 정확하고 간결하게 답변하세요."

_DEFAULT_PROMPT_TMPL = Template(
    "다음 참고 문서를 바탕으로 질문에 답하세요.\n\n"
    "=== 참고 문서 ===\n"
    "$context\n"
    "=================\n\n"
    "질문: $question\n\n"
    "답변:"
)

_NO_CONTEXT_TMPL = Template(
    "질문: $question\n\n"
    "답변:"
)


class RAGChain:
    """
    RAGPipeline + OllamaManager를 연결하는 LangChain 스타일 체인.

    체인 흐름:
        질문 입력
          → RAGPipeline.query() 로 관련 문서 검색
          → 프롬프트 템플릿에 컨텍스트 삽입
          → OllamaManager.enqueue() 로 Qwen2.5 추론
          → 답변 반환
    """

    def __init__(
        self,
        rag: RAGPipeline | None = None,
        manager: OllamaManager | None = None,
        top_k: int = 5,
        system_prompt: str = _DEFAULT_SYSTEM,
        prompt_template: Template = _DEFAULT_PROMPT_TMPL,
        use_rag: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        self.rag              = rag or RAGPipeline()
        self._manager         = manager  # None이면 ask() 호출 시 get_manager() 사용
        self.top_k            = top_k
        self.system_prompt    = system_prompt
        self.prompt_template  = prompt_template
        self.use_rag          = use_rag
        self.temperature      = temperature
        self.max_tokens       = max_tokens
        logger.info(
            "RAGChain 초기화 — top_k=%d, use_rag=%s, temp=%.2f",
            top_k, use_rag, temperature,
        )

    # ── 공개 API ─────────────────────────────────────────────

    def ask(
        self,
        question: str,
        priority: int = 5,
        timeout: float = 120,
        extra_context: str | None = None,
    ) -> str:
        """
        동기 추론. 결과 텍스트 반환.

        Args:
            question:      사용자 질문
            priority:      InferenceQueue 우선순위 (0=긴급, 5=기본, 9=배치)
            timeout:       최대 대기 시간(초)
            extra_context: RAG 외 추가 컨텍스트 (선택)
        """
        fut = self.ask_async(question, priority=priority, extra_context=extra_context)
        return fut.result(timeout=timeout)

    async def ask_stream(
        self,
        question: str,
        extra_context: str | None = None,
    ):
        """
        비동기 제너레이터 — 토큰 단위로 스트리밍 반환.
        Ollama /api/generate 의 stream=True 모드를 직접 사용.

        사용 예:
            async for token in chain.ask_stream("질문"):
                print(token, end="", flush=True)
        """
        import asyncio
        import json
        import requests as _req

        prompt = self._build_prompt(question, extra_context)
        mgr = self._get_manager()

        payload = {
            "model":      mgr.model,
            "prompt":     prompt,
            "stream":     True,
            "keep_alive": mgr.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt

        # 동기 HTTP 스트리밍을 별도 스레드에서 실행해 이벤트 루프를 막지 않음
        loop = asyncio.get_event_loop()
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _stream_worker():
            try:
                with _req.post(
                    f"{mgr.base_url}/api/generate",
                    json=payload,
                    stream=True,
                    timeout=120,
                ) as resp:
                    resp.raise_for_status()
                    for raw_line in resp.iter_lines():
                        if not raw_line:
                            continue
                        try:
                            data = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        token = data.get("response", "")
                        if token:
                            loop.call_soon_threadsafe(token_queue.put_nowait, token)
                        if data.get("done", False):
                            break
            except Exception as exc:
                logger.error("ask_stream 오류: %s", exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)  # 종료 신호

        # 별도 스레드에서 HTTP 스트리밍 실행
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, _stream_worker)

        # 토큰 하나씩 yield
        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield token

    def ask_async(
        self,
        question: str,
        priority: int = 5,
        extra_context: str | None = None,
    ) -> Future:
        """
        비동기 추론. Future 즉시 반환.
        future.result(timeout=...) 로 답변 수신.
        """
        prompt = self._build_prompt(question, extra_context)
        mgr = self._get_manager()
        logger.info(
            "RAGChain 요청 전송 — priority=%d, prompt_len=%d",
            priority, len(prompt),
        )
        return mgr.enqueue(
            prompt=prompt,
            priority=priority,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """RAGPipeline에 문서 추가 (편의 메서드)"""
        self.rag.add_documents(texts, metadatas, ids)

    # ── 내부 메서드 ──────────────────────────────────────────

    def _build_prompt(self, question: str, extra_context: str | None) -> str:
        """RAG 검색 → 컨텍스트 조립 → 프롬프트 생성"""
        context_parts: list[str] = []

        # 1) RAG 검색
        if self.use_rag and self.rag.doc_count > 0:
            retrieved = self.rag.query_texts(question, top_k=self.top_k)
            if retrieved:
                context_parts.extend(
                    f"[{i}] {text}" for i, text in enumerate(retrieved, 1)
                )
                logger.debug("RAG 컨텍스트 %d개 삽입", len(retrieved))

        # 2) 추가 컨텍스트
        if extra_context:
            context_parts.append(extra_context)

        # 3) 프롬프트 조합
        if context_parts:
            context_str = "\n".join(context_parts)
            return self.prompt_template.safe_substitute(
                context=context_str,
                question=question,
            )
        else:
            # 문서 없음 → 컨텍스트 없이 직접 질문
            return _NO_CONTEXT_TMPL.safe_substitute(question=question)

    def _get_manager(self) -> OllamaManager:
        if self._manager is not None:
            return self._manager
        return get_manager()

    # ── 디버그 헬퍼 ──────────────────────────────────────────

    def preview_prompt(self, question: str, extra_context: str | None = None) -> str:
        """실제 전송될 프롬프트를 미리 확인 (추론 없이)"""
        return self._build_prompt(question, extra_context)


# ── 간단 CLI 테스트 ───────────────────────────────────────────
if __name__ == "__main__":
    import tempfile, shutil, os

    print("\n" + "═" * 55)
    print("  RAGChain 프롬프트 조립 테스트 (Ollama 연결 없이)")
    print("═" * 55 + "\n")

    tmp = tempfile.mkdtemp()
    try:
        rag = RAGPipeline(
            persist_dir=os.path.join(tmp, "chroma"),
            bm25_path=os.path.join(tmp, "bm25.pkl"),
            use_reranker=False,
        )
        rag.add_documents([
            "PlanQuest는 완전 로컬 AI 개인 비서 프로젝트입니다.",
            "Ollama를 사용해 Qwen2.5 모델을 로컬에서 실행합니다.",
            "ChromaDB와 BM25를 결합한 하이브리드 RAG를 사용합니다.",
        ])

        # OllamaManager 없이 프롬프트만 미리보기
        chain = RAGChain(rag=rag, manager=None, top_k=2)
        prompt = chain.preview_prompt("이 프로젝트에서 어떤 모델을 쓰나요?")

        print("생성된 프롬프트:")
        print("─" * 40)
        print(prompt)
        print("─" * 40)

        assert "Ollama" in prompt or "Qwen" in prompt or "PlanQuest" in prompt, \
            "RAG 컨텍스트가 프롬프트에 포함되지 않음"
        assert "질문:" in prompt
        assert "답변:" in prompt
        print("\n✅ 프롬프트 조립 정상")

        # 컨텍스트 없는 경우
        empty_rag = RAGPipeline(
            persist_dir=os.path.join(tmp, "chroma2"),
            bm25_path=os.path.join(tmp, "bm25_2.pkl"),
            use_reranker=False,
        )
        chain2 = RAGChain(rag=empty_rag, manager=None)
        prompt2 = chain2.preview_prompt("안녕?")
        assert "참고 문서" not in prompt2
        assert "질문: 안녕?" in prompt2
        print("✅ 문서 없을 때 단순 프롬프트 정상")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n✅ 모든 테스트 통과")
    print("═" * 55)
    print("  실제 Ollama 추론 테스트:")
    print("  python rag_chain.py 를 Ollama 서버 실행 후 사용")
    print("═" * 55)
