"""Plan-Quest - FastAPI 백엔드 메인"""
import signal
import sys
import os
import logging
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


# ─── 패키징 (PyInstaller) 환경 감지 ─────────────────────
def _is_frozen() -> bool:
    """PyInstaller 로 패키징된 상태인지."""
    return getattr(sys, "frozen", False)


def _frontend_build_dir():
    """프론트 build 폴더 경로 (있으면). PyInstaller 와 dev 모두 대응."""
    candidates = []
    if _is_frozen():
        # PyInstaller datas 로 묶여서 _MEIPASS/frontend_build 에 들어감
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "frontend_build")
        # 또는 exe 옆 (--onedir)
        candidates.append(Path(sys.executable).parent / "frontend_build")
    # dev 환경
    candidates.append(Path(__file__).resolve().parent.parent / "frontend" / "build")

    for c in candidates:
        if c.exists() and (c / "index.html").exists():
            return c
    return None

from database import engine, Base
from seed_data import seed_database
from ollama_manager import start_ollama_server, stop_ollama_server, is_ollama_installed

from routers import (
    user, habits, trees, shop, placement, chat,
    memory, proactive, calendar, insights, notifications,
    suggestions, feedback,  # W6 추가
)

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
app.include_router(memory.router)
app.include_router(proactive.router)
app.include_router(calendar.router)
app.include_router(insights.router)
app.include_router(notifications.router)
app.include_router(suggestions.router)  # W6 D1-2
app.include_router(feedback.router)      # W6 D4


# ─── 프론트 정적 파일 서빙 (PyInstaller 패키지 시 필수) ──
_frontend_dir = _frontend_build_dir()
if _frontend_dir:
    logger.info(f"📦 프론트 정적 파일 서빙: {_frontend_dir}")
    # /assets, /static 같은 React 빌드 파일들
    app.mount("/static", StaticFiles(directory=str(_frontend_dir / "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """API 가 아닌 모든 경로는 index.html 로 (React Router 대응)."""
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            # API 라우터 도달 전이라면 404 가 자연스러움
            from fastapi import HTTPException
            raise HTTPException(404)
        target = _frontend_dir / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        # SPA fallback — 모든 미매칭 → index.html
        return FileResponse(_frontend_dir / "index.html")
else:
    logger.info("ℹ️ 프론트 build 폴더 없음 — npm start 로 별도 실행 필요")


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
