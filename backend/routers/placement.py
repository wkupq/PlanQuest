"""Plan-Quest - 아이템 배치 라우터 + 시간당 하트 생성."""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import OwnedItem, PlacedItem, ShopItem, UserProfile
from schemas import PlaceItemRequest, PlacedItemResponse

router = APIRouter(prefix="/api", tags=["배치"])

# 배치도 사이즈
GRID_COLS = 7
GRID_ROWS = 5


# ─── 등급별 하트 생성 설정 ─────────────────────────────
# (interval_hours, hearts_per_tick)
RARITY_HEART_CONFIG = {
    "common":    (6, 1),   # 6시간마다 1하트
    "rare":      (4, 2),   # 4시간마다 2하트
    "unique":    (3, 3),   # 3시간마다 3하트 ← 신규 등급
    "epic":      (2, 4),   # 2시간마다 4하트
    "legendary": (1, 6),   # 1시간마다 6하트
}


def _compute_pending_hearts(p: PlacedItem) -> int:
    """배치 시점부터 또는 마지막 수확 이후 누적된 하트 수."""
    if not p.owned_item or not p.owned_item.shop_item:
        return 0
    rarity = p.owned_item.shop_item.rarity or "common"
    interval_h, amount = RARITY_HEART_CONFIG.get(rarity, (6, 1))

    last = p.last_heart_gen or p.placed_at or datetime.utcnow()
    elapsed = datetime.utcnow() - last
    ticks = int(elapsed.total_seconds() / (interval_h * 3600))
    # 최대 24 ticks 까지만 누적 (방치 시 무한 누적 방지)
    ticks = min(ticks, 24)
    return ticks * amount


def _validate_grid(x: int, y: int):
    if not (0 <= x < GRID_COLS and 0 <= y < GRID_ROWS):
        raise HTTPException(400, f"좌표가 그리드 밖입니다 ({GRID_COLS}x{GRID_ROWS}): ({x},{y})")


def _to_response(p: PlacedItem) -> PlacedItemResponse:
    item = p.owned_item.shop_item if p.owned_item else None
    return PlacedItemResponse(
        id=p.id,
        owned_item_id=p.owned_item_id,
        grid_x=p.grid_x,
        grid_y=p.grid_y,
        item_name=item.name if item else "(?)",
        item_emoji=item.emoji if item else "",
        item_image_url=(item.image_url if item else "") or "",
        item_category=item.category if item else "character",
        rarity=item.rarity if item else "common",
        pending_hearts=_compute_pending_hearts(p),
    )


# ─── 조회 ──────────────────────────────────────────────
@router.get("/placed-items", response_model=List[PlacedItemResponse])
def get_placed_items(db: Session = Depends(get_db)):
    placed = db.query(PlacedItem).all()
    return [_to_response(p) for p in placed if p.owned_item and p.owned_item.shop_item]


# ─── 배치 (인벤토리에서 — owned_item_id = ShopItem.id) ─
@router.post("/placed-items", response_model=PlacedItemResponse)
def place_item(req: PlaceItemRequest, db: Session = Depends(get_db)):
    _validate_grid(req.grid_x, req.grid_y)

    # 프론트가 보내는 owned_item_id 는 ShopItem.id (legacy)
    owned = db.query(OwnedItem).filter(
        OwnedItem.shop_item_id == req.owned_item_id,
        OwnedItem.user_id == 1
    ).first()
    if not owned:
        raise HTTPException(404, "소유하지 않은 아이템입니다")

    # 이미 배치된 아이템이면 위치만 갱신
    existing = db.query(PlacedItem).filter(PlacedItem.owned_item_id == owned.id).first()
    if existing:
        existing.grid_x = req.grid_x
        existing.grid_y = req.grid_y
        db.commit()
        return _to_response(existing)

    # 새 배치 — last_heart_gen 은 지금 시각 (배치 직후엔 하트 X)
    placed = PlacedItem(
        user_id=1,
        owned_item_id=owned.id,
        grid_x=req.grid_x,
        grid_y=req.grid_y,
        last_heart_gen=datetime.utcnow(),
    )
    db.add(placed)
    db.commit()
    db.refresh(placed)
    return _to_response(placed)


# ─── 이동 (PlacedItem.id 기준 — 정확한 캐릭터 이동) ────
class MoveRequest(BaseModel):
    grid_x: int
    grid_y: int


@router.patch("/placed-items/{placed_id}/position")
def move_placed_item(placed_id: int, req: MoveRequest, db: Session = Depends(get_db)):
    """배치된 캐릭터를 새 좌표로 이동.
    PlacedItem.id 기준 — 다른 캐릭터와 헷갈리지 않음."""
    _validate_grid(req.grid_x, req.grid_y)

    placed = db.query(PlacedItem).filter(PlacedItem.id == placed_id).first()
    if not placed:
        raise HTTPException(404, "배치된 아이템 없음")

    # 충돌 체크 (자기 자신 제외)
    conflict = db.query(PlacedItem).filter(
        PlacedItem.id != placed_id,
        PlacedItem.grid_x == req.grid_x,
        PlacedItem.grid_y == req.grid_y,
    ).first()
    if conflict:
        raise HTTPException(409, "이미 다른 캐릭터가 있는 자리입니다")

    placed.grid_x = req.grid_x
    placed.grid_y = req.grid_y
    db.commit()
    return {"message": "이동 완료", "grid_x": req.grid_x, "grid_y": req.grid_y}


# ─── 수확 (시간당 누적 하트 받기) ──────────────────────
@router.post("/placed-items/{placed_id}/harvest")
def harvest_placed(placed_id: int, db: Session = Depends(get_db)):
    """배치 캐릭터의 누적 하트 수확."""
    placed = db.query(PlacedItem).filter(PlacedItem.id == placed_id).first()
    if not placed:
        raise HTTPException(404, "배치된 캐릭터 없음")

    pending = _compute_pending_hearts(placed)
    if pending <= 0:
        raise HTTPException(400, "수확할 하트가 아직 없어요. 조금만 더 기다려보세요.")

    user = db.query(UserProfile).first()
    user.hearts += pending
    user.total_hearts_earned += pending
    user.level = (user.total_hearts_earned // 10) + 1

    placed.last_heart_gen = datetime.utcnow()
    db.commit()

    item = placed.owned_item.shop_item if placed.owned_item else None
    return {
        "message": f"💗 {item.name if item else '캐릭터'} 에서 하트 {pending}개 수확!",
        "harvested": pending,
        "total_hearts": user.hearts,
        "level": user.level,
    }


# ─── 제거 (회수) ────────────────────────────────────────
@router.delete("/placed-items/{placed_id}")
def remove_placed_item(placed_id: int, db: Session = Depends(get_db)):
    placed = db.query(PlacedItem).filter(PlacedItem.id == placed_id).first()
    if not placed:
        raise HTTPException(404, "배치된 아이템을 찾을 수 없습니다")
    db.delete(placed)
    db.commit()
    return {"message": "아이템 배치 해제"}
