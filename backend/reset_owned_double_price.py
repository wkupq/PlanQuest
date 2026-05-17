"""
보유/배치 캐릭터 전부 초기화 + 모든 캐릭터 가격 2배.

영향:
  - OwnedItem 전체 삭제 (구매 기록 X)
  - PlacedItem 전체 삭제 (배치 X)
  - ShopItem.price 모두 ×2
  - UserProfile (하트/레벨/누적) 그대로 유지
  - Habit, TreeOnMap 도 그대로 유지

사용법:
  cd backend
  python reset_owned_double_price.py
  python reset_owned_double_price.py --dry-run   # 미리보기만
"""
import argparse
from database import SessionLocal
from models import OwnedItem, PlacedItem, ShopItem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 미리보기만")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # 현재 상태
        n_owned = db.query(OwnedItem).count()
        n_placed = db.query(PlacedItem).count()
        n_shop = db.query(ShopItem).count()
        print(f"[현재] 보유={n_owned}, 배치={n_placed}, 상점={n_shop}")

        # 가격 2배 미리보기
        print(f"\n[가격 변경 미리보기]")
        for item in db.query(ShopItem).filter_by(category="character").all():
            new_price = item.price * 2
            print(f"  {item.emoji} {item.name:10s} {item.price:>3}H → {new_price:>3}H")

        if args.dry_run:
            print("\n[dry-run] 실제 변경 없이 종료.")
            return

        # 1) 배치 → 보유 순서대로 삭제 (FK)
        db.query(PlacedItem).delete()
        db.query(OwnedItem).delete()
        print(f"\n[삭제] 배치 {n_placed}개, 보유 {n_owned}개 모두 정리")

        # 2) ShopItem 가격 2배
        items = db.query(ShopItem).all()
        for item in items:
            item.price = item.price * 2
        print(f"[가격] {len(items)}개 아이템 가격 ×2")

        db.commit()

        # 결과
        print(f"\n[after] 보유={db.query(OwnedItem).count()}, 배치={db.query(PlacedItem).count()}")
        print(f"\n새 가격표:")
        for item in db.query(ShopItem).filter_by(category="character").order_by(ShopItem.price).all():
            print(f"  {item.emoji} {item.name:10s} {item.price:>3}H · {item.rarity:10s} · Lv.{item.unlock_level}")
        print("\n✅ 완료")
    finally:
        db.close()


if __name__ == "__main__":
    main()
