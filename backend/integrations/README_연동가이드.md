# 외부 서비스 연동 가이드

이 폴더의 클라이언트들은 **스캐폴드 상태**입니다. 자격증명을 끼워 넣어야 동작합니다.

---

## 📅 Google Calendar

### 1단계: Google Cloud Console 설정

1. https://console.cloud.google.com 접속
2. 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 → 라이브러리** → "Google Calendar API" 검색 → **사용 설정**
4. **API 및 서비스 → OAuth 동의 화면**
   - User Type: **External**
   - 앱 이름: "Plan-Quest"
   - 사용자 지원 이메일: 본인 이메일
   - **테스트 사용자**에 본인 이메일 추가 (꼭 필요!)
5. **API 및 서비스 → 사용자 인증 정보**
   - **사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 이름: "Plan-Quest Desktop"
   - **JSON 다운로드** 클릭

### 2단계: 다운로드한 파일 배치

다운로드된 `client_secret_xxx.json` 파일을:
```
C:\Users\guswl\.plan-quest\credentials.json
```
위치에 **`credentials.json`** 이름으로 저장.

(폴더 없으면 만들기: `mkdir %USERPROFILE%\.plan-quest`)

### 3단계: 첫 실행 — 동의

```bash
python -c "from integrations.google_calendar import get_calendar_client; c = get_calendar_client(); print('READY' if c.is_ready() else c.setup_instructions())"
```

브라우저 창이 열림 → Google 계정 선택 → 권한 동의.
끝나면 `~/.plan-quest/calendar_token.json` 자동 생성.

### 4단계: 코드에서 사용

```python
from integrations.google_calendar import get_calendar_client
from datetime import datetime

client = get_calendar_client()
if client.is_ready():
    events = client.list_events(start=datetime.now(), days=7)
    for e in events:
        print(e["summary"], e["start"])
```

---

## ✉️ Gmail / 이메일

### 옵션 A — Gmail API (권장)

위 Calendar 와 동일한 절차. `credentials.json` 은 한 번만 받으면
Calendar 와 Gmail 양쪽에 사용 가능 (단, OAuth 동의 화면에서 Gmail scope 도 추가 필요).

OAuth 동의 화면 → **범위 추가**:
- `.../auth/gmail.readonly`

### 옵션 B — IMAP (간단)

**Gmail 의 경우:**

1. https://myaccount.google.com/security
2. **2단계 인증** 켜기 (꼭 필요)
3. **앱 비밀번호** 생성 → "메일", "Windows 컴퓨터" 선택
4. 16자리 비밀번호 복사

**환경변수 설정 (PowerShell):**

```powershell
[Environment]::SetEnvironmentVariable("PLAN_QUEST_EMAIL", "your@gmail.com", "User")
[Environment]::SetEnvironmentVariable("PLAN_QUEST_EMAIL_APP_PASSWORD", "16자리앱비밀번호", "User")
```

다른 메일 서비스면:
```powershell
[Environment]::SetEnvironmentVariable("PLAN_QUEST_EMAIL_IMAP_HOST", "imap.naver.com", "User")
```

설정 후 PowerShell 재시작.

### 사용

```python
from integrations.email_client import get_email_client

client = get_email_client()
if client.is_ready():
    print(f"모드: {client.mode}")  # "gmail_api" 또는 "imap"
    recent = client.list_recent(max_results=5)
    for m in recent:
        print(m["subject"], "←", m["sender"])
else:
    print(client.setup_instructions())
```

---

## 🔌 AI 도구 (`tools/calendar_tools.py`, `tools/email_tools.py`) 와 연결

현재 도구들은 mock 데이터 반환. 실제 연동하려면 도구 함수를 실 클라이언트로 교체:

```python
# backend/tools/calendar_tools.py 의 search_calendar() 등을:
from integrations.google_calendar import get_calendar_client

def search_calendar(query: str = "") -> str:
    client = get_calendar_client()
    if not client.is_ready():
        return f"[캘린더 미연동]\n{client.setup_instructions()}"
    events = client.search_events(query, days=30)
    if not events:
        return "관련 일정 없음"
    return "\n".join(f"- {e['start']}: {e['summary']}" for e in events)
```

같은 패턴을 `tools/email_tools.py` 에도 적용.

---

## 🔒 자격증명 보안

| 파일 | 절대 깃에 올리면 안 됨 |
|------|----------------------|
| `~/.plan-quest/credentials.json` | OAuth client secret |
| `~/.plan-quest/calendar_token.json` | 사용자 access token |
| `~/.plan-quest/gmail_token.json` | 동일 |
| 환경변수 `PLAN_QUEST_EMAIL_APP_PASSWORD` | IMAP 비밀번호 |

`.gitignore` 확인:
```
.plan-quest/
*token*.json
credentials.json
```

---

## 🧪 빠른 테스트

연동 상태 한 번에 확인:

```python
# backend/test_integrations.py
from integrations.google_calendar import get_calendar_client
from integrations.email_client import get_email_client

cal = get_calendar_client()
print(f"📅 Google Calendar: {'✅ 연결됨' if cal.is_ready() else '❌ 미연동'}")

email = get_email_client()
print(f"✉️ Email: {'✅ ' + email.mode if email.is_ready() else '❌ 미연동'}")
```
