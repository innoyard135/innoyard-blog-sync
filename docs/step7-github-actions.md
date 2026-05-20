# STEP 7 — GitHub Actions (Mac 없이 1시간마다 자동 발송)

## 개요

- **트리거:** 매시 정각(UTC) + 수동 실행(`workflow_dispatch`)
- **동작:** `python -m src.poll_notion` — Notion `게시준비` ☑ + `상태=대기` 행 처리
- **설정 파일:** 저장소의 `config.github.yaml` → CI에서 `config.yaml`로 복사
- **비밀:** GitHub Secrets 4개 (`.env`는 푸시하지 않음)

---

## 1. Private 저장소 만들기

1. GitHub → **New repository**
2. 이름 예: `innoyard-blog-sync`
3. **Private** 선택
4. README / .gitignore 추가 **하지 않음** (빈 repo)

---

## 2. 로컬에서 푸시 (최초 1회)

터미널에서 `blog-sync` 폴더로 이동 후:

```bash
cd "/Users/wooyoung/Desktop/클로드 코드 파일/이노야드/blog-sync"

git init
git add .
git status   # .env, .venv, config.yaml, output/ 가 목록에 없어야 함
git commit -m "Add blog-sync pipeline and GitHub Actions workflow"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USER>/innoyard-blog-sync.git
git push -u origin main
```

`<YOUR_GITHUB_USER>` 를 본인 계정으로 바꾸세요.

---

## 3. GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 (로컬 `.env`와 동일) |
|-------------|-------------------------|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `NOTION_TOKEN` | Notion Integration Secret |
| `TELEGRAM_BOT_TOKEN` | BotFather 토큰 |
| `TELEGRAM_CHAT_ID` | 그룹 chat id (예: `-5066982541`) |

이름은 **대소문자까지** 위와 같아야 합니다.

---

## 4. Actions 활성화

1. 저장소 **Actions** 탭
2. 워크플로 비활성화 안내가 있으면 **Enable workflows**
3. 왼쪽 **Poll Notion manuscripts** → **Run workflow** → **Run workflow** (수동 1회 테스트)

---

## 5. 성공 확인

- **Actions** 실행 로그: `처리할 원고 없음` 또는 `→ 발송완료 처리`
- **Telegram** 그룹에 `.docx` 도착
- **Notion** 해당 행 `발송완료` + `telegram 발송일`

테스트용 행을 다시 쓰려면 Notion에서 `상태`를 **대기**로 되돌리고 `게시준비`를 다시 체크하세요.

---

## 6. 스케줄 (한국 시간)

cron `0 * * * *` 는 **UTC 매시 0분**에 실행됩니다.

한국(KST, UTC+9)에서는 **매시 정각**(9:00, 10:00, 11:00 …)에 맞춰 돌아갑니다.  
예: UTC 0:00 → KST 9:00, UTC 1:00 → KST 10:00.

다른 시각에 맞추려면 `.github/workflows/poll-notion.yml` 의 `cron` 값을 [crontab.guru](https://crontab.guru/) 로 조정하세요.

---

## 7. Notion / config 변경 시

| 변경 내용 | 수정 위치 |
|-----------|-----------|
| DB ID, 컬럼명 | `config.github.yaml` 커밋 후 push |
| API 키·토큰 | GitHub Secrets만 수정 (코드 푸시 불필요) |

---

## 문제 해결

| 증상 | 확인 |
|------|------|
| `config.yaml 이 없습니다` | 워크플로에 `cp config.github.yaml config.yaml` 단계 있는지 |
| Telegram 실패 | Secrets 이름·값, 그룹에 봇 초대 여부 |
| Notion 400 | `database_id`가 **DB** ID인지 (페이지 ID 아님) |
| 원고 없음 | `게시준비` ☑ + `상태=대기` 인 행 있는지 |

---

## 보안

- `.env`는 **절대** 커밋하지 마세요 (`.gitignore`에 포함됨).
- 토큰이 채팅에 노출됐다면 BotFather / Anthropic / Notion에서 **재발급** 후 Secrets 갱신.
