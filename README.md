# 원고 재가공 → Word → 메신저 자동화

이노야드 **원고(초안)** 를 전문의 톤으로 재가공하고, **Word(.docx)** 로 저장한 뒤 **텔레그램**(또는 카카오 텍스트)으로 보냅니다.  
Word 말미에는 일반인이 잘 떠올리지 못하는 **추가 콘텐츠 아이템**(사두증·단두·사경·수면자세 등)이 붙습니다.

## 워크플로우

세 가지 입력 모드를 지원합니다.

```
A) manuscripts/*.md|.txt|.docx
B) --file <path>
C) --notion-url <URL>           ← 이 모드가 카카오톡 링크 알림과 짝
        ↓ Claude 재가공
output/docx/YYYYMMDD_제목.docx
  +  Notion 결과 페이지 자동 생성 (옵션)
        ↓
Telegram: .docx 파일 + 캡션              ✅
Kakao:    링크 카드 + 콘텐츠 아이템 요약 ✅ (Notion 페이지 URL)
```

## Notion → 카카오톡 링크 모드 (이번에 추가)

```bash
python -m src.pipeline --notion-url "https://www.notion.so/xxxxxxxxxxxx"
```

- 원고: Notion 페이지를 API로 읽음 (Integration 공유 필요)
- 결과: 같은 워크스페이스 안의 **부모 페이지** 아래에 새 페이지 생성
- 카카오톡 「나에게 보내기」 로 **노션 페이지 링크 카드** 도착 → 클릭 시 노션 앱에서 열림

## 설치

```bash
cd blog-sync
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env
# .env 편집
```

## 실행

```bash
# manuscripts/ 안의 모든 원고 처리
python -m src.pipeline

# 한 파일만
python -m src.pipeline --file manuscripts/example_원고.md

# Word만 만들고 메신저 생략
python -m src.pipeline --no-notify

# 이미 처리한 원고 다시
python -m src.pipeline --force
```

처리가 끝나면 원고는 `manuscripts/_done/` 으로 이동합니다 (`--no-move` 로 유지 가능).

## Word 파일 구성

1. **재가공 본문** — 전문의 톤, 의료광고 주의 표현 반영  
2. **추가 콘텐츠 아이템 제안** — 주제 / 훅 / 전문가 각도 / 왜 놓치기 쉬운가  
3. **면책 문구**

## Telegram 설정 (파일 자동 전송 · 권장)

1. [@BotFather](https://t.me/BotFather) 에서 봇 생성 → `TELEGRAM_BOT_TOKEN`
2. 봇과 대화 한 번 시작
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` 에서 `chat.id` → `TELEGRAM_CHAT_ID`
4. `config.yaml` 의 `notify.provider: telegram`

## Kakao 설정 (나에게 보내기 + 노션 링크)

카카오 API는 파일 첨부를 지원하지 않으므로, **노션 결과 페이지 링크**를 보내는 방식이 가장 현실적입니다.

1. [Kakao Developers](https://developers.kakao.com) → 내 애플리케이션 생성
2. **플랫폼 등록** (Web: `http://localhost`) — 토큰 발급용
3. **카카오 로그인 활성화** + 동의 항목: `talk_message` (카카오톡 메시지 전송)
4. **REST API 키**로 인가 코드 받기:
   ```
   https://kauth.kakao.com/oauth/authorize?response_type=code&client_id=<REST_API_KEY>&redirect_uri=http://localhost&scope=talk_message
   ```
   브라우저에서 로그인 → 리다이렉트 URL의 `?code=xxx` 복사
5. 토큰 발급:
   ```bash
   curl -X POST "https://kauth.kakao.com/oauth/token" \
     -d "grant_type=authorization_code" \
     -d "client_id=<REST_API_KEY>" \
     -d "redirect_uri=http://localhost" \
     -d "code=<위에서 받은 code>"
   ```
   응답의 `access_token` → `.env` 의 `KAKAO_ACCESS_TOKEN`
6. `config.yaml` 에 `notify.provider: kakao` (또는 `both`)

토큰은 보통 **6시간** 유효합니다. 장기 자동화는 `refresh_token` 으로 재발급하는 단계가 추가로 필요합니다 (필요 시 요청).

## Notion Integration 설정 (원고 읽기 + 결과 페이지 만들기)

1. <https://www.notion.so/profile/integrations> → **New integration** (Internal)
2. **Internal Integration Secret** 복사 → `.env` 의 `NOTION_TOKEN`
3. 원고가 있는 **Notion 페이지** 우상단 `...` → **연결 → 방금 만든 integration 추가**
4. 결과를 저장할 **부모 페이지** 도 같은 방식으로 integration 공유, 페이지 URL에서 32자리 ID 부분만 추출해 `config.yaml` 의 `notion.result_parent_page_id` 에 입력

## config.yaml 예시

```yaml
target:
  author_label: "성형외과·소아과 전문의"

manuscripts:
  dir: manuscripts
  move_after_process: true

notify:
  provider: telegram
```

## 원고 형식

| 형식 | 비고 |
|------|------|
| `.md` | 첫 줄 `# 제목` 선택 |
| `.txt` | 파일명을 제목으로 |
| `.docx` | 첫 단락=제목, 이후=본문 |

## 네이버 RSS 모드 (이전 기능)

```bash
python -m src.main --dry-run
```

## Notion DB 폴링 (게시준비 + 대기)

```bash
python -m src.poll_notion --dry-run   # 조회만
python -m src.poll_notion             # 재가공 → Word → Telegram → 발송완료
```

DB·컬럼 설정: `docs/step6-notion-db-setup.md`

## GitHub Actions (Mac 없이 자동화)

1시간마다 `poll_notion` 실행: **STEP 7** 가이드 → `docs/step7-github-actions.md`

- 워크플로: `.github/workflows/poll-notion.yml`
- CI 설정: `config.github.yaml` (Secrets는 GitHub에만 등록)

## 법적 검수

자동 결과는 **반드시 의사·법무 검수** 후 게시하세요. `_context/brand_guidelines.md` 참고.

## 폴더 구조

```
manuscripts/          ← 원고 넣기
manuscripts/_done/    ← 처리 완료
output/docx/          ← 생성 Word
prompts/              ← LLM 지시문
data/content_topic_bank.yaml
```
