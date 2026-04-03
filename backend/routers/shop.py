"""Plan-Quest - 상점 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import UserProfile, ShopItem, OwnedItem
from schemas import ShopItemResponse

router = APIRouter(prefix="/api", tags=["상점"])


@router.get("/shop", response_model=List[ShopItemResponse])
def get_shop_items(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ShopItem)
    if category:
        query = query.filter(ShopItem.category == category)
    items = query.all()

    owned_ids = {o.shop_item_id for o in db.query(OwnedItem).filter(OwnedItem.user_id == 1).all()}

    result = []
    for item in items:
        resp = ShopItemResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            price=item.price,
            emoji=item.emoji,
            description=item.description,
            rarity=item.rarity,
            unlock_level=item.unlock_level,
            owned=item.id in owned_ids,
        )
        result.append(resp)
    return result


@router.post("/shop/{item_id}/buy")
def buy_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ShopItem).filter(ShopItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")

    user = db.query(UserProfile).first()

    if user.level < item.unlock_level:
        raise HTTPException(status_code=400, detail=f"레벨 {item.unlock_level} 이상 필요합니다")
    if user.hearts < item.price:
        raise HTTPException(status_code=400, detail="하트가 부족합니다")

    existing = db.query(OwnedItem).filter(
        OwnedItem.user_id == 1, OwnedItem.shop_item_id == item_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 소유한 아이템입니다")

    user.hearts -= item.price
    owned = OwnedItem(user_id=1, shop_item_id=item_id)
    db.add(owned)
    db.commit()
    db.refresh(owned)

    return {
        "message": f"'{item.name}' 구매 완료!",
        "remaining_hearts": user.hearts,
        "owned_item_id": owned.id,
    }
