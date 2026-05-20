"""Plan-Quest — WebSocket 실시간 알림.

엔드포인트:
  WS  /ws/notifications     — 클라이언트가 연결하면 백그라운드에서 능동 추천 + 알람 시간 푸시
  POST /api/notifications/send — 서버에서 즉시 알림 push (디버그/테스트용)

흐름:
  1) 클라이언트 WebSocket 연결
  2) 서버는 ConnectionManager 에 등록
  3) 백그라운드 task 가 30초마다:
     - 새 능동 추천 (proactive_ai) 체크 → 변화 있으면 push
     - 일정 알람 시간 매치 (HH:MM 일치) → push
  4) 클라 종료/타임아웃 시 자동 정리

JSON 메시지 형식:
  {"type": "suggestion", "data": {...}}
  {"type": "alarm", "data": {"habit_id": 1, "title": "...", "time": "09:00"}}
  {"type": "ping"}  ← 30초마다 keepalive
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from proactive_ai import get_proactive_suggestions
from models import Habit


router = APIRouter(tags=["알림"])


class ConnectionManager:
    """WebSocket 연결 관리."""

    def __init__(self):
        self.active: List[WebSocket] = []
        # 사용자별 마지막 추천 hash (변화 감지용)
        self.last_suggestions: Dict[str, str] = {}
        # 오늘 이미 알림 보낸 알람 키 (hh:mm + habit_id)
        self.alarms_sent_today: Set[str] = set()
        self.alarms_date = datetime.now().date()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        # 연결 직후 환영 + 현재 상태 push
        await ws.send_json({"type": "connected", "data": {"timestamp": datetime.now().isoformat()}})

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, msg: Dict):
        """모든 연결에 push. 끊긴 연결 자동 제거."""
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def reset_daily_alarms(self):
        """날짜 바뀌면 알람 추적 리셋."""
        today = datetime.now().date()
        if today != self.alarms_date:
            self.alarms_sent_today.clear()
            self.alarms_date = today


manager = ConnectionManager()


# ─── 백그라운드 폴러 ─────────────────────────────────────
async def background_pusher():
    """주기적으로 능동 추천 / 알람 시간 체크 → push."""
    while True:
        try:
            await asyncio.sleep(30)  # 30초마다

            if not manager.active:
                continue

            manager.reset_daily_alarms()

            # 1) 능동 추천 변화 체크
            db = SessionLocal()
            try:
                suggestions = get_proactive_suggestions(db, user_id=1)
                # hash 비교 (변화 있을 때만 push)
                sig = json.dumps([(s["type"], s["title"]) for s in suggestions], sort_keys=True)
                if sig != manager.last_suggestions.get("user_1"):
                    manager.last_suggestions["user_1"] = sig
                    if suggestions:  # 새 추천 있을 때만
                        await manager.broadcast({
                            "type": "suggestion",
                            "data": suggestions[:3],  # top 3 만
                        })

                # 2) 알람 시간 매치 체크
                now = datetime.now()
                hh_mm = now.strftime("%H:%M")
                krDow = now.weekday()

                habits = db.query(Habit).all()
                for h in habits:
                    if not h.alarm_enabled:
                        continue
                    rd = h.repeat_days or []
                    if rd and krDow not in rd:
                        continue
                    for t in (h.times or []):
                        if t == hh_mm:
                            key = f"{h.id}:{hh_mm}"
                            if key not in manager.alarms_sent_today:
                                manager.alarms_sent_today.add(key)
                                await manager.broadcast({
                                    "type": "alarm",
                                    "data": {
                                        "habit_id": h.id,
                                        "title": h.title,
                                        "time": t,
                                    },
                                })
            finally:
                db.close()

        except Exception as e:
            print(f"[notifications] background error: {e}")


# 앱 시작 시 백그라운드 task 시작
_bg_task = None


def start_background():
    global _bg_task
    if _bg_task is None or _bg_task.done():
        loop = asyncio.get_event_loop()
        _bg_task = loop.create_task(background_pusher())


# ─── WebSocket 엔드포인트 ───────────────────────────────
@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """클라이언트 WebSocket 연결.

    클라 측 코드 예시 (JS):
        const ws = new WebSocket('ws://localhost:8000/ws/notifications');
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            if (msg.type === 'suggestion') showToast(msg.data[0].title);
            if (msg.type === 'alarm')      showAlarm(msg.data.title);
        };
    """
    await manager.connect(websocket)
    start_background()
    try:
        while True:
            # 클라가 보내는 메시지는 그냥 echo (디버그용) + ping 응답
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─── 디버그용 즉시 push ──────────────────────────────────
@router.post("/api/notifications/test")
async def test_push(message: str = "테스트 알림"):
    """모든 연결된 클라이언트에 테스트 메시지 푸시."""
    await manager.broadcast({
        "type": "test",
        "data": {"message": message, "timestamp": datetime.now().isoformat()},
    })
    return {"sent_to": len(manager.active)}
