"""
테스트용 하트 추가 스크립트.

사용법:
  cd backend
  python add_hearts.py            # 10개 추가
  python add_hearts.py 50          # 50개 추가
  python add_hearts.py 100 --level 5  # 100개 추가 + 레벨 5
  python add_hearts.py -5           # 5개 차감
  python add_hearts.py --reset      # 0으로 리셋

백엔드 켜져 있어도/꺼져 있어도 OK (DB 직접 조작).
"""
import sys
import argparse
from database import SessionLocal
from models import UserProfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("count", nargs="?", type=int, default=10,
                        help="추가할 하트 수 (음수면 차감, 기본 10)")
    parser.add_argument("--level", type=int, default=None,
                        help="레벨 직접 설정 (선택)")
    parser.add_argument("--reset", action="store_true",
                        help="하트 0, 레벨 1로 초기화")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(UserProfile).first()
        if not user:
            print("❌ 사용자 정보가 없습니다. 백엔드를 한 번 실행해서 DB 생성하세요.")
            return

        print(f"[before] hearts={user.hearts}, level={user.level}, total={user.total_hearts_earned}")

        if args.reset:
            user.hearts = 0
            user.total_hearts_earned = 0
            user.level = 1
            print("[action] 리셋")
        else:
            user.hearts = max(0, user.hearts + args.count)
            if args.count > 0:
                user.total_hearts_earned += args.count
                user.level = (user.total_hearts_earned // 10) + 1
            print(f"[action] 하트 {args.count:+}")

        if args.level is not None:
            user.level = max(1, args.level)
            print(f"[action] 레벨 = {args.level}")

        db.commit()
        print(f"[after]  hearts={user.hearts}, level={user.level}, total={user.total_hearts_earned}")
        print("✅ 완료")
    finally:
        db.close()


if __name__ == "__main__":
    main()
