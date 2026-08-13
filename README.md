# 인삼 농장 AI 영농일지 플랫폼

인삼 재배 농가를 위한 AI 병해충 진단 · 영농일지 모바일 앱과, 농자재 회사가 회원 농가를 모니터링하고
친환경 자재를 처방·제안하는 데 사용하는 관리자 웹 대시보드로 구성된 풀스택 플랫폼입니다.

```
┌────────────────────┐        ┌──────────────────────┐        ┌───────────────────────┐
│   Flutter 모바일 앱   │ ─────▶ │   FastAPI 백엔드 서버   │ ◀───── │   관리자 웹 대시보드     │
│ (농가용, iOS/Android) │  REST  │  (Gemini · OpenWeather │  REST  │ (농자재사용, HTML/JS)   │
└────────────────────┘        │   연동, SQLite)         │        └───────────────────────┘
                               └──────────────────────┘
                                         │
                                  SQLite + 업로드 사진
```

## 구성

| 폴더 | 스택 | 역할 |
|---|---|---|
| [`backend/`](backend/README.md) | Python / FastAPI | 농장·영농일지·AI진단 API, Gemini/OpenWeather 연동, PDF 리포트 |
| [`mobile/`](mobile/README.md) | Flutter | 농가용 모바일 앱 (iOS/Android) |
| [`admin_dashboard/`](admin_dashboard/README.md) | HTML/JS (Chart.js, Leaflet) | 농자재 회사용 모니터링 대시보드 |

## 빠른 시작 (데모)

API 키가 없어도 `DEMO_MODE=true`(기본값) 상태로 전체 기능을 바로 체험할 수 있습니다.
백엔드 최초 실행 시 6개 농가(금산·풍기·강화·진안·장수·음성)와 영농일지 70여 건, AI 진단 30여 건이
자동으로 시딩됩니다.

### 1) 백엔드 실행

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

→ http://localhost:8000/docs 에서 API 문서 확인

### 2) 관리자 대시보드 실행

```bash
cd admin_dashboard
python3 -m http.server 8080
```

→ http://localhost:8080 접속 (종합 현황 / 지역별 발생 지도 / 농가 모니터링 / 실시간 피드 / 처방 알림)

### 3) 모바일 앱 실행

```bash
cd mobile
flutter create . --project-name ginseng_farm_app --org com.ginsengfarm   # 최초 1회
flutter pub get
flutter run
```

자세한 권한 설정은 [`mobile/README.md`](mobile/README.md) 참고.

## 데모 시나리오 예시

1. **모바일 앱**에서 농장을 등록한다 (예: 금산군, 해가림 시설, 4년근, 1500평).
2. **영농일지** 탭에서 오늘 진행한 작업(예: "해가림 시설 점검")을 사진과 함께 기록한다 — 날짜·작업면적이
   자동으로 채워진다.
3. **AI진단** 탭에서 병해충 의심 부위 사진을 찍어 업로드한다. 앱이 사진의 EXIF GPS/촬영시각을 추출해
   서버로 전송하면, 서버가 OpenWeather로 당시 기상을 조회하고 Gemini 1.5 Flash로 사진+기상+자체
   친환경 DB를 종합 분석해 **친환경 자재 우선 추천 + 화학적 관리법 보조 정보**를 반환한다.
4. **통계** 탭에서 유형별/월별 발생 추이와 TOP5 병해충을 확인하고, 기간을 지정해 PDF 리포트를 내려받는다.
5. **관리자 대시보드**에서 해당 농가의 진단 이력이 실시간 피드에 나타나는 것을 확인하고, 위험도가
   높은 농가에 "친환경 자재 처방 알림"을 전송한다 — 알림은 모바일 앱 홈 화면에 즉시 표시된다.

## 실제 API 키 연동

`backend/.env`에서 `DEMO_MODE=false`로 바꾸고 `GEMINI_API_KEY`(Google AI Studio),
`OPENWEATHER_API_KEY`를 입력하면 실제 Gemini 1.5 Flash / OpenWeather API를 호출합니다.
호출 실패 시 자동으로 데모 응답으로 폴백하므로 서비스가 중단되지 않습니다.

## 데이터

- `backend/app/data/eco_treatment_db.json` — 자체 친환경/유기농 방제 자재 DB 샘플 (병해 3종, 해충 2종,
  생리장애 2종). Gemini 진단 프롬프트에 컨텍스트로 포함되어, 진단 결과와 매칭되는 자사 자재를
  최우선으로 추천합니다.
- `backend/app/seed.py` — 시연용 가상 데이터 시더 (농가 6곳, 영농일지, AI 진단, 처방 알림).
