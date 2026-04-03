"""
ollama_manager.py — Ollama 웜업 · keep_alive · InferenceQueue
--------------------------------------------------------------
사용법:
    from ollama_manager import OllamaManager

    mgr = OllamaManager()          # 모델 자동 감지 (model_config.txt)
    mgr.start()                    # 웜업 + keep_alive + 큐 워커 시작

    # 우선순위 추론 요청 (낮을수록 먼저 처리)
    future = mgr.enqueue(prompt="안녕?", priority=0)
    result = future.result(timeout=120)   # concurrent.futures.Future

    mgr.stop()                     # 종료
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

# ── 로거 ─────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── 상수 ─────────────────────────────────────────────────────
DEFAULT_BASE_URL   = "http://127.0.0.1:11434"
DEFAULT_KEEP_ALIVE = "10m"          # Ollama keep_alive 파라미터
WARMUP_PROMPT      = "ping"         # 웜업용 최소 프롬프트
WARMUP_TIMEOUT     = 60             # 웜업 최대 대기(초)
HEALTH_INTERVAL    = 30             # keep_alive 헬스체크 주기(초)
MAX_WORKERS        = 2              # 동시 추론 워커 수
MAX_QUEUE_SIZE     = 50             # 큐 최대 적재량
REQUEST_TIMEOUT    = 120            # 추론 HTTP 타임아웃(초)


# ── 우선순위 큐 아이템 ────────────────────────────────────────
@dataclass(order=True)
class _QueueItem:
    priority: int
    # priority가 같을 때 seq로 FIFO 보장 (Future는 비교 불가라 field 제외)
    seq: int = field(compare=True)
    prompt: str = field(compare=False)
    options: dict = field(compare=False)
    future: Future = field(compare=False)


# ── OllamaManager ────────────────────────────────────────────
class OllamaManager:
    """
    Ollama 서버와의 통신을 담당하는 싱글턴 매니저.

    기능:
    - 웜업: 서버 기동 후 첫 응답까지 블로킹 대기
    - keep_alive: 주기적 ping으로 모델 언로드 방지
    - InferenceQueue: PriorityQueue + threading으로 요청 직렬화/병렬화
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
        max_workers: int = MAX_WORKERS,
    ) -> None:
        self.base_url   = base_url.rstrip("/")
        self.keep_alive = keep_alive
        self.max_workers = max_workers

        # 모델 이름: 인자 → model_config.txt → 기본값
        self.model = model or self._load_model_config() or "qwen2.5:7b"
        logger.info("OllamaManager 초기화 — 모델: %s", self.model)

        self._pq: queue.PriorityQueue[_QueueItem] = queue.PriorityQueue(
            maxsize=MAX_QUEUE_SIZE
        )
        self._seq_counter = 0
        self._seq_lock    = threading.Lock()

        self._workers: list[threading.Thread] = []
        self._keep_alive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready      = threading.Event()   # 웜업 완료 플래그

    # ── 공개 API ─────────────────────────────────────────────

    def start(self, warmup: bool = True) -> None:
        """웜업 + keep_alive + 큐 워커 스레드 시작"""
        if warmup:
            self._warmup()

        # 큐 워커
        for i in range(self.max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"ollama-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

        # keep_alive 헬스체크 스레드
        self._keep_alive_thread = threading.Thread(
            target=self._keep_alive_loop,
            name="ollama-keep-alive",
            daemon=True,
        )
        self._keep_alive_thread.start()

        logger.info(
            "OllamaManager 시작 완료 — 워커 %d개, keep_alive 간격 %ds",
            self.max_workers, HEALTH_INTERVAL,
        )

    def stop(self) -> None:
        """워커·keep_alive 스레드 정리"""
        logger.info("OllamaManager 종료 중...")
        self._stop_event.set()

        # 워커 종료용 sentinel 투입
        for _ in self._workers:
            try:
                self._pq.put_nowait(
                    _QueueItem(priority=999, seq=0,
                               prompt="", options={}, future=Future())
                )
            except queue.Full:
                pass

        for t in self._workers:
            t.join(timeout=5)

        if self._keep_alive_thread:
            self._keep_alive_thread.join(timeout=5)

        logger.info("OllamaManager 종료 완료")

    def enqueue(
        self,
        prompt: str,
        priority: int = 5,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **extra_options: Any,
    ) -> Future:
        """
        추론 요청을 우선순위 큐에 넣고 Future 반환.

        priority: 낮을수록 먼저 처리 (0 = 긴급, 5 = 기본, 9 = 배치)
        반환된 Future.result() 로 응답 텍스트를 받음.

        Raises:
            queue.Full: 큐가 꽉 찬 경우
        """
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            **extra_options,
        }
        if system:
            options["system"] = system

        future: Future = Future()

        with self._seq_lock:
            seq = self._seq_counter
            self._seq_counter += 1

        item = _QueueItem(
            priority=priority,
            seq=seq,
            prompt=prompt,
            options=options,
            future=future,
        )

        try:
            self._pq.put_nowait(item)
        except queue.Full as exc:
            future.set_exception(exc)
            logger.warning("추론 큐가 꽉 찼습니다 (maxsize=%d)", MAX_QUEUE_SIZE)

        logger.debug(
            "요청 큐 등록 — seq=%d priority=%d qsize=%d",
            seq, priority, self._pq.qsize(),
        )
        return future

    @property
    def queue_size(self) -> int:
        return self._pq.qsize()

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    # ── 내부 메서드 ──────────────────────────────────────────

    def _load_model_config(self) -> str | None:
        """setup_model.py가 저장한 model_config.txt 읽기"""
        config_path = Path(__file__).parent / "model_config.txt"
        if config_path.exists():
            model = config_path.read_text(encoding="utf-8").strip()
            logger.info("model_config.txt 로드: %s", model)
            return model
        return None

    # ── 웜업 ─────────────────────────────────────────────────

    def _warmup(self) -> None:
        """
        Ollama 서버가 응답할 때까지 블로킹 대기 후
        최소 프롬프트로 모델을 메모리에 로드.
        """
        logger.info("웜업 시작 — 서버: %s, 모델: %s", self.base_url, self.model)
        deadline = time.time() + WARMUP_TIMEOUT

        # 1) 서버 헬스 대기
        while time.time() < deadline:
            if self._ping_server():
                break
            logger.debug("Ollama 서버 응답 대기 중...")
            time.sleep(2)
        else:
            raise RuntimeError(
                f"Ollama 서버가 {WARMUP_TIMEOUT}초 내에 응답하지 않았습니다. "
                f"'ollama serve' 가 실행 중인지 확인하세요."
            )

        # 2) 모델 로드 (최소 프롬프트로 generate)
        logger.info("모델 로드 중 (keep_alive=%s)...", self.keep_alive)
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model":      self.model,
                    "prompt":     WARMUP_PROMPT,
                    "stream":     False,
                    "keep_alive": self.keep_alive,
                    "options":    {"num_predict": 1},
                },
                timeout=WARMUP_TIMEOUT,
            )
            resp.raise_for_status()
            logger.info("✅ 웜업 완료 — 모델이 메모리에 로드됨")
        except requests.RequestException as exc:
            raise RuntimeError(f"웜업 중 오류 발생: {exc}") from exc

        self._ready.set()

    def _ping_server(self) -> bool:
        """GET /api/tags 로 서버 생존 확인"""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    # ── keep_alive 헬스체크 ──────────────────────────────────

    def _keep_alive_loop(self) -> None:
        """
        주기적으로 최소 요청을 보내 모델이 메모리에서 언로드되지 않도록 유지.
        Ollama 기본 언로드 타임아웃(5분)보다 짧은 주기로 실행.
        """
        logger.info("keep_alive 스레드 시작 (간격: %ds)", HEALTH_INTERVAL)
        while not self._stop_event.wait(timeout=HEALTH_INTERVAL):
            if not self._ping_server():
                logger.warning("keep_alive: Ollama 서버 응답 없음")
                continue

            try:
                requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model":      self.model,
                        "prompt":     WARMUP_PROMPT,
                        "stream":     False,
                        "keep_alive": self.keep_alive,
                        "options":    {"num_predict": 1},
                    },
                    timeout=10,
                )
                logger.debug("keep_alive ping 완료")
            except requests.RequestException as exc:
                logger.warning("keep_alive ping 실패: %s", exc)

    # ── 워커 루프 ────────────────────────────────────────────

    def _worker_loop(self) -> None:
        """우선순위 큐에서 아이템을 꺼내 추론 실행"""
        thread_name = threading.current_thread().name
        logger.info("%s 시작", thread_name)

        while not self._stop_event.is_set():
            try:
                item: _QueueItem = self._pq.get(timeout=1)
            except queue.Empty:
                continue

            # sentinel: 빈 프롬프트 = 종료 신호
            if not item.prompt:
                self._pq.task_done()
                break

            logger.debug(
                "%s 처리 중 — seq=%d priority=%d",
                thread_name, item.seq, item.priority,
            )

            if item.future.cancelled():
                self._pq.task_done()
                continue

            try:
                result = self._infer(item.prompt, item.options)
                item.future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                logger.error("%s 추론 오류 — seq=%d: %s",
                             thread_name, item.seq, exc)
                item.future.set_exception(exc)
            finally:
                self._pq.task_done()

        logger.info("%s 종료", thread_name)

    def _infer(self, prompt: str, options: dict) -> str:
        """
        Ollama /api/generate 호출 후 응답 텍스트 반환.
        system 프롬프트가 options에 있으면 분리해서 전달.
        """
        system = options.pop("system", None)

        payload: dict[str, Any] = {
            "model":      self.model,
            "prompt":     prompt,
            "stream":     False,
            "keep_alive": self.keep_alive,
            "options":    options,
        }
        if system:
            payload["system"] = system

        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # 응답 구조: {"response": "...", "done": true, ...}
        response_text = data.get("response", "")
        if not response_text:
            raise ValueError(f"빈 응답 수신: {data}")

        logger.debug(
            "추론 완료 — %d 토큰 생성 (eval_count=%s)",
            len(response_text),
            data.get("eval_count", "?"),
        )
        return response_text


# ── 싱글턴 헬퍼 ──────────────────────────────────────────────
_instance: OllamaManager | None = None
_instance_lock = threading.Lock()


def get_manager(**kwargs: Any) -> OllamaManager:
    """
    프로세스 전역 싱글턴 OllamaManager 반환.
    첫 호출 시 start()까지 자동 실행.
    """
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = OllamaManager(**kwargs)
            _instance.start()
    return _instance


# ── 간단 CLI 테스트 ───────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OllamaManager 테스트")
    parser.add_argument("--model",  default=None,  help="모델 이름 (기본: model_config.txt)")
    parser.add_argument("--prompt", default="안녕하세요! 한 문장으로 자기소개 해줘.",
                        help="테스트 프롬프트")
    parser.add_argument("--priority", type=int, default=0, help="우선순위 (0=최고)")
    args = parser.parse_args()

    print("\n" + "═" * 55)
    print("  OllamaManager 동작 테스트")
    print("═" * 55)

    mgr = OllamaManager(model=args.model)
    mgr.start(warmup=True)

    print(f"\n📨 요청 전송: '{args.prompt}' (priority={args.priority})")
    fut = mgr.enqueue(prompt=args.prompt, priority=args.priority)

    print("⏳ 응답 대기 중...")
    try:
        answer = fut.result(timeout=120)
        print(f"\n✅ 응답:\n{answer}")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
    finally:
        mgr.stop()

    print("\n" + "═" * 55)
