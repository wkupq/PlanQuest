"""Plan-Quest - 아이템 배치 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import OwnedItem, PlacedItem
from schemas import PlaceItemRequest, PlacedItemResponse

router = APIRouter(prefix="/api", tags=["배치"])


@router.get("/placed-items", response_model=List[PlacedItemResponse])
def get_placed_items(db: Session = Depends(get_db)):
    placed = db.query(PlacedItem).all()
    result = []
    for p in placed:
        owned = db.query(OwnedItem).filter(OwnedItem.id == p.owned_item_id).first()
        if owned and owned.shop_item:
            item = owned.shop_item
            result.append(PlacedItemResponse(
                id=p.id,
                owned_item_id=p.owned_item_id,
                grid_x=p.grid_x,
                grid_y=p.grid_y,
                item_name=item.name,
                item_emoji=item.emoji,
                item_category=item.category,
            ))
    return result


@router.post("/placed-items", response_model=PlacedItemResponse)
def place_item(req: PlaceItemRequest, db: Session = Depends(get_db)):
    # req.owned_item_id는 프론트에서 ShopItem.id로 전달됨
    # → OwnedItem.shop_item_id로 조회해야 함
    owned = db.query(OwnedItem).filter(
        OwnedItem.shop_item_id == req.owned_item_id,
        OwnedItem.user_id == 1
    ).first()
    if not owned:
        raise HTTPException(status_code=404, detail="소유하지 않은 아이템입니다")

    # 이미 배치된 아이템인지 확인 (OwnedItem.id 기준)
    existing = db.query(PlacedItem).filter(PlacedItem.owned_item_id == owned.id).first()
    if existing:
        existing.grid_x = req.grid_x
        existing.grid_y = req.grid_y
        db.commit()
        item = owned.shop_item
        return PlacedItemResponse(
            id=existing.id, owned_item_id=existing.owned_item_id,
            grid_x=existing.grid_x, grid_y=existing.grid_y,
            item_name=item.name, item_emoji=item.emoji, item_category=item.category,
        )

    placed = PlacedItem(user_id=1, owned_item_id=owned.id, grid_x=req.grid_x, grid_y=req.grid_y)
    db.add(placed)
    db.commit()
    db.refresh(placed)

    item = owned.shop_item
    return PlacedItemResponse(
        id=placed.id, owned_item_id=placed.owned_item_id,
        grid_x=placed.grid_x, grid_y=placed.grid_y,
        item_name=item.name, item_emoji=item.emoji, item_category=item.category,
    )


@router.delete("/placed-items/{placed_id}")
def remove_placed_item(placed_id: int, db: Session = Depends(get_db)):
    placed = db.query(PlacedItem).filter(PlacedItem.id == placed_id).first()
    if not placed:
        raise HTTPException(status_code=404, detail="배치된 아이템을 찾을 수 없습니다")
    db.delete(placed)
    db.commit()
    return {"message": "아이템 배치 해제"}
