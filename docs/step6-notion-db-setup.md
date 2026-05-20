# STEP 6 — 노션 원고 DB 만들기 (직접 생성)

## 1. DB 만들기 (5분)

1. 노션에서 원하는 위치(예: `이노야드 마케팅`)에 **새 페이지** 생성
2. 페이지 안에 `/database` 입력 → **Table - Full page** 선택
3. DB 이름: **`원고 자동화`** (원하는 이름 OK, config에 ID만 맞으면 됨)

## 2. 컬럼 추가 (이름·타입 정확히)

| 컬럼 이름 | 타입 | 설정 |
|-----------|------|------|
| **제목** | Title | (기본 제목 컬럼 이름을 `제목`으로 변경) |
| **게시 준비** | Checkbox | 기본값: 체크 해제 |
| **상태** | Select | 옵션: `대기` , `발송완료` (이 두 개만) |
| **Telegram 발송일** | Date | (선택, 자동 기록용) |

> 컬럼 이름은 **띄어쓰기·한글 그대로** — 코드가 이 이름으로 조회합니다.

## 3. 원고 쓰는 방법

1. DB에 **새 행** 추가 → **제목** 입력 (예: `우리 아이 두상, 괜찮을까요`)
2. 그 **행(제목)을 클릭** → 열리는 **노션 페이지**에 본문 작성 (B 방식)
3. 초안 완료 후 **「게시 준비」 체크** ☑
4. **「상태」** 는 `대기` 로 두기 (기본값)

→ 1시간 이내(또는 수동 실행 시 즉시) 자동 재가공 + 텔레그램 발송  
→ 완료되면 **상태**가 `발송완료`로 바뀜

## 4. Notion Integration 연결

1. <https://www.notion.so/profile/integrations> → **New integration**
2. 이름: `innoyard-blog-sync` → **Internal** → Submit
3. **Internal Integration Secret** 복사 → `.env` 의 `NOTION_TOKEN=`
4. **원고 자동화 DB 페이지** 우상단 `···` → **연결(Connections)** → 방금 integration 추가

## 5. Database ID 복사

DB를 **전체 페이지**로 연 뒤 브라우저 URL:

```
https://www.notion.so/워크스페이스/36679185e0a48069b0fef49d683602a8?v=...
```

`notion.so/` 와 `?` 사이의 **32자리 hex** (하이픈 있거나 없거나)  
또는 DB 열기 → `···` → **Copy link** → 링크에서 ID 추출

`config.yaml` 에 입력:

```yaml
notion:
  database_id: "여기에-32자리-ID"
```

## 6. 테스트 실행

```bash
cd blog-sync
source .venv/bin/activate
python -m src.poll_notion --dry-run   # 조회만
python -m src.poll_notion             # 실제 발송
```

## 체크리스트

- [ ] DB 컬럼: 제목 / 게시 준비 / 상태(대기·발송완료)
- [ ] Integration 생성 + DB에 연결
- [ ] NOTION_TOKEN → .env
- [ ] database_id → config.yaml
- [ ] 테스트 행 1개 + 게시 준비 체크 + poll 실행
