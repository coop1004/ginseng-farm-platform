# 백엔드 API 서버 (FastAPI)

인삼 농장 AI 영농일지 앱 및 관리자 대시보드가 공용으로 사용하는 REST API 서버입니다.

## 실행

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # 필요 시 GEMINI_API_KEY / OPENWEATHER_API_KEY 입력

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

최초 실행 시 SQLite DB(`ginseng_farm.db`)가 자동 생성되고, 데모용 농가 6곳 + 영농일지/AI진단 목업
데이터가 자동으로 시딩됩니다 (`app/seed.py`). API 문서는 http://localhost:8000/docs 에서 확인할 수 있습니다.

## 환경변수 (`.env`)

| 변수 | 설명 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio에서 발급한 Gemini API 키 |
| `OPENWEATHER_API_KEY` | OpenWeather API 키 |
| `DEMO_MODE` | `true`(기본값)이면 API 키 없이도 시나리오 기반 시뮬레이션 응답으로 동작 |
| `DATABASE_URL` | 기본값 SQLite 파일 |
| `UPLOAD_DIR` | 업로드된 사진 저장 경로 |
| `JWT_SECRET` | 로그인 토큰 서명 키. **공개 저장소이므로 운영 배포 시 반드시 재정의할 것** (Render는 자동 생성) |
| `CRON_SECRET` | 날씨 수집 배치 엔드포인트 보호용 시크릿 (아래 참고) |

`DEMO_MODE=false` + 두 API 키를 모두 입력하면 실제 Gemini 1.5 Flash / OpenWeather API를 호출합니다.
Gemini 호출이 실패하면 자동으로 DB 기반 데모 진단으로 폴백합니다.

## 주요 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET/POST | `/api/farms` | 농장 등록/조회 |
| PUT/DELETE | `/api/farms/{id}` | 농장 수정/삭제 |
| GET/POST | `/api/work-logs` | 영농작업 일지 (사진 업로드 지원, multipart) |
| GET/POST | `/api/diagnoses` | AI 병해충/생리장애 진단 (사진 업로드 → EXIF → 기상 → Gemini) |
| GET | `/api/stats/summary` | 통계 요약 (유형별/월별/TOP5/AI정확도) |
| GET | `/api/stats/calendar` | 캘린더용 일자별 건수 |
| GET | `/api/reports/farms/{id}/pdf` | 농장별 기간 리포트 PDF 다운로드 |
| GET | `/api/admin/farms/overview` | 관리자용 농가별 현황 요약 |
| GET | `/api/admin/regional-stats` | 관리자용 지역별 발생 집계 |
| GET | `/api/admin/feed` | 관리자용 실시간 진단 피드 |
| GET/POST | `/api/admin/notifications` | 처방 알림 이력/전송 |
| POST | `/api/admin/weather/collect` | 전체 농장 오늘자 기상 스냅샷 수집 (배치, 아래 참고) |
| GET | `/api/admin/weather/history` | 축적된 일별 기상 기록 조회 |

## 날씨 데이터 축적 (병해충-기상 상관관계 분석용)

AI 진단 시점에만 날씨를 기록하면, 진단이 없었던 날의 기상 상태(예: "장마 3일째")를 알 수 없어
"어떤 기상 패턴이 병해충 발생으로 이어지는지" 같은 사후 분석이 어렵습니다. 그래서 진단 여부와
무관하게 **매일 모든 농장의 기상을 스냅샷으로 쌓는** `WeatherRecord` 테이블을 별도로 둡니다.

- `POST /api/admin/weather/collect` — 등록된 모든 농장의 오늘자 기상을 수집해 저장. 이미 오늘자
  기록이 있는 농장은 건너뛰므로(멱등) 하루에 여러 번 호출해도 안전합니다.
- 실시간 스트리밍이 아니라 **일 1회 스냅샷 축적** 방식입니다(OpenWeather 무료 티어 기준 현실적인
  방식). 매일 자동 호출되도록 `.github/workflows/collect-weather.yml`에 GitHub Actions 스케줄러를
  구성해뒀습니다(한국시간 매일 오전 6시).

### 자동 수집 활성화 방법

1. Render 백엔드 서비스 → `Environment` 탭에서 `CRON_SECRET` 값 확인(자동 생성됨)
2. GitHub 저장소 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
   - Name: `WEATHER_CRON_SECRET`
   - Value: 1번에서 확인한 값
3. 이후 매일 자동 실행되며, `Actions` 탭에서 `Run workflow` 버튼으로 수동 실행도 가능합니다.

## 친환경 방제 자재 DB

`app/data/eco_treatment_db.json` — 병해 3종, 해충 2종, 생리장애 2종에 대한 자체 친환경/화학적 관리법
샘플 데이터입니다. Gemini 진단 시 이 DB를 프롬프트 컨텍스트로 함께 전달하여, DB에 등록된 자재를
최우선으로 추천하도록 구성되어 있습니다.
