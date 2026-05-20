"""Plan-Quest - FastAPI 백엔드 메인"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from seed_data import seed_database

from routers import user, habits, trees, shop, placement, chat

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def _run_google_sync_background() -> None:
    """서버 시작 시 백그라운드에서 Google 동기화 1회 실행"""
    try:
        from google_sync import run_sync
        result = run_sync()
        logger.info(
            "서버 시작 시 Google 동기화 완료 — Calendar: %d, Gmail: %d",
            result["calendar"], result["gmail"],
        )
        if result["error"]:
            logger.warning("동기화 중 오류: %s", result["error"])
    except Exception as e:
        # Google 미인증 등 실패해도 서버 시작은 계속
        logger.warning("Google 동기화 건너뜀 (인증 없음 또는 오류): %s", e)


def _start_scheduler() -> None:
    """APScheduler로 30분마다 Google 동기화 예약"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from google_sync import run_sync

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_sync,
            trigger="interval",
            minutes=30,
            id="google_sync",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler 시작 — Google 동기화 30분마다 실행")
    except ImportError:
        logger.warning("apscheduler 미설치 — 자동 동기화 비활성화 (pip install apscheduler)")
    except Exception as e:
        logger.warning("스케줄러 시작 실패: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행되는 lifespan 핸들러"""
    # 시작
    # 백그라운드 스레드로 Google 동기화 (서버 응답 지연 방지)
    sync_thread = threading.Thread(
        target=_run_google_sync_background,
        name="google-sync-startup",
        daemon=True,
    )
    sync_thread.start()

    # APScheduler 시작
    _start_scheduler()

    yield
    # 종료 시 추가 정리 작업 (필요 시)


# DB 초기화 + 시드
Base.metadata.create_all(bind=engine)
seed_database()

app = FastAPI(title="Plan-Quest API", version="1.0.0", lifespan=lifespan)

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


@app.get("/api/sync/google")
async def manual_google_sync():
    """수동 Google 동기화 트리거 (테스트용)"""
    try:
        from google_sync import run_sync
        result = run_sync()
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
