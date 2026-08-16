// "바탕화면에 바로가기" 설치(Add to Home Screen)를 브라우저가 허용하려면
// 활성화된 서비스워커가 있어야 한다(크롬 설치 조건). 오프라인 캐싱은 하지 않고
// 네트워크 요청을 그대로 통과시키기만 한다 - 대시보드는 항상 최신 데이터를
// 서버에서 받아야 하므로 캐싱하면 오히려 오래된 화면을 보여주는 문제가 생긴다.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
