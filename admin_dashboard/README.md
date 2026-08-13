# 관리자 웹 대시보드

농자재 회사가 회원 농가의 영농일지·병해충 발생 현황을 실시간으로 모니터링하고,
친환경 자재 처방 알림을 전송할 수 있는 정적 HTML/JS 대시보드입니다. 별도 빌드 과정이 필요 없습니다.

## 실행

백엔드 서버(`../backend`)가 먼저 실행 중이어야 합니다.

```bash
cd admin_dashboard
python3 -m http.server 8080
```

브라우저에서 http://localhost:8080 접속. 좌측 하단에서 API 서버 주소(기본 `http://localhost:8000`)를 확인/변경할 수 있습니다.

## 구성

- `index.html` — 레이아웃 (종합 현황 / 지역별 발생 지도 / 농가 모니터링 / 실시간 피드 / 처방 알림 이력)
- `js/api.js` — 백엔드 REST API 클라이언트
- `js/dashboard.js` — 차트(Chart.js)·지도(Leaflet) 렌더링 및 알림 전송 로직
- `css/style.css` — 스타일

외부 라이브러리(Chart.js, Leaflet)는 CDN에서 로드합니다.
