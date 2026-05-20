import sqlite3
import json
from datetime import datetime, timedelta
from calendar_module import get_recent_5_events_raw

DB_PATH = "assistant.db"

def init_cache_table():
    """캐시 저장용 테이블 초기화"""
    # with 문을 사용하여 자동으로 연결을 닫습니다.
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_cache (
                id TEXT PRIMARY KEY,
                data TEXT,
                last_sync TIMESTAMP
            )
        ''')
        conn.commit()

def get_cached_calendar():
    """캐시된 일정을 가져오거나 API를 통해 동기화합니다."""
    # 연결을 열 때 with 문을 사용하면 함수가 끝날 때 자동으로 닫힙니다.
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. 기존 캐시 데이터 확인
        cursor.execute("SELECT data, last_sync FROM calendar_cache WHERE id = 'primary_events'")
        row = cursor.fetchone()
        
        now = datetime.now()
        should_sync = True
        
        # 2. 30분 경과 여부 확인
        if row:
            last_sync = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S.%f')
            if now - last_sync < timedelta(minutes=30):
                should_sync = False
        
        # 3. 동기화 로직
        if should_sync:
            try:
                print("새로운 일정을 구글 서버에서 가져옵니다...")
                new_events = get_recent_5_events_raw() 
                
                # 최신 데이터로 업데이트 (last_sync 포함)
                cursor.execute('''
                    INSERT OR REPLACE INTO calendar_cache (id, data, last_sync)
                    VALUES (?, ?, ?)
                ''', ('primary_events', json.dumps(new_events), now.strftime('%Y-%m-%d %H:%M:%S.%f')))
                conn.commit()
                return new_events
            except Exception as e:
                print(f"오프라인 상태이거나 오류 발생: {e}. 기존 캐시를 사용합니다.")
                return json.loads(row[0]) if row else []
        else:
            print("최근 30분 이내에 동기화되었습니다. 캐시 데이터를 사용합니다.")
            return json.loads(row[0])

if __name__ == '__main__':
    # 테이블 초기화 및 데이터 조회 실행
    init_cache_table()
    events = get_cached_calendar()
    
    print(f"--- 조회 결과 ({len(events)}개) ---")
    for event in events:
        print(f"일정: {event.get('summary')}")