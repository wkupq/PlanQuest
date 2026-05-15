"""Plan-Quest - FastAPI 백엔드 메인"""
import signal
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from seed_data import seed_database
from ollama_manager import start_ollama_server, stop_ollama_server, is_ollama_installed

from routers import user, habits, trees, shop, placement, chat

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("plan-quest")


# ─── Lifespan: 시작/종료 이벤트 관리 ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan 핸들러
    - 시작 시: DB 초기화, 시드 데이터, Ollama 자동 시작
    - 종료 시: Ollama 프로세스 정리, DB 연결 해제
    """
    # ── 시작 (startup) ──
    logger.info("🚀 Plan-Quest 서버를 시작합니다...")

    # DB 초기화 + 시드
    Base.metadata.create_all(bind=engine)
    seed_database()
    logger.info("✅ 데이터베이스 초기화 완료")

    # Ollama 자동 시작 시도
    if is_ollama_installed():
        logger.info("🤖 Ollama 서버 자동 시작 시도...")
        started = start_ollama_server()
        if started:
            logger.info("✅ Ollama 서버 연결 완료")
        else:
            logger.warning("⚠️ Ollama 서버 시작 실패 (수동으로 실행해주세요)")
    else:
        logger.warning("⚠️ Ollama가 설치되어 있지 않습니다 (AI 채팅 제한)")

    logger.info("=" * 50)
    logger.info("  Plan-Quest API 서버 준비 완료!")
    logger.info("  http://127.0.0.1:8000")
    logger.info("  Ctrl+C 로 안전하게 종료할 수 있습니다")
    logger.info("=" * 50)

    yield  # ← 여기서 앱이 실행됨

    # ── 종료 (shutdown) ──
    logger.info("🛑 Plan-Quest 서버를 종료합니다...")

    # Ollama 프로세스 정리
    stop_ollama_server()

    # DB 엔진 정리
    engine.dispose()
    logger.info("✅ 데이터베이스 연결 해제")

    logger.info("👋 Plan-Quest 서버 종료 완료. 안녕!")


# ─── FastAPI 앱 생성 ───
app = FastAPI(
    title="Plan-Quest API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(user.router)
app.include_router(habits.router)
app.include_router(trees.router)
app.include_router(shop.router)
app.include_router(placement.router)
app.include_router(chat.router)


# ─── SIGTERM/SIGINT 핸들러 (Ctrl+C 안전 종료) ───
def _signal_handler(signum, frame):
    """시그널 수신 시 깔끔하게 종료"""
    sig_name = signal.Signals(signum).name
    logger.info(f"\n📡 {sig_name} 시그널 수신 — 안전 종료를 시작합니다...")
    # Ollama 정리 (lifespan shutdown 전에 미리 정리)
    stop_ollama_server()
    sys.exit(0)


# 시그널 핸들러 등록
signal.signal(signal.SIGINT, _signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, _signal_handler)  # kill/docker stop


if __name__ == "__main__":
    import uvicorn

    logger.info("🎮 Plan-Quest 서버를 더블클릭으로 실행했습니다!")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
