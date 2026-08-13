# 인삼 AI 영농일지 (Flutter 모바일 앱)

인삼 농장 전용 AI 병해충 진단 및 영농일지 앱입니다. `lib/` 하위의 Dart 소스만 포함되어 있으며,
플랫폼(android/ios) 프로젝트 폴더는 최초 1회 `flutter create .` 명령으로 생성해야 합니다.
(이 개발 환경에는 Flutter SDK가 설치되어 있지 않아 플랫폼 폴더를 직접 실행/검증하지 못했습니다.)

## 1. 최초 설정

```bash
cd mobile
flutter create . --project-name ginseng_farm_app --org com.ginsengfarm
flutter pub get
```

위 명령은 기존 `lib/`, `pubspec.yaml`을 보존하면서 `android/`, `ios/` 폴더를 생성합니다.

## 2. 권한 설정 추가

### Android — `android/app/src/main/AndroidManifest.xml`
`<manifest>` 태그 바로 아래(= `<application>` 태그 위)에 추가:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
```

### iOS — `ios/Runner/Info.plist`
`<dict>` 안에 추가:

```xml
<key>NSCameraUsageDescription</key>
<string>병해충 진단 및 작업 기록 사진 촬영을 위해 카메라 접근이 필요합니다.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>진단 사진 첨부를 위해 사진 라이브러리 접근이 필요합니다.</string>
```

## 3. 백엔드 서버 주소 설정

기본값은 다음과 같습니다 (`lib/services/app_config.dart`):
- Android 에뮬레이터: `http://10.0.2.2:8000`
- iOS 시뮬레이터 / 웹: `http://localhost:8000`
- 실제 기기(폰)로 테스트할 경우: 앱 실행 후 홈 화면 우측 상단 ⚙️ 설정에서 PC의 사설 IP(`http://192.168.x.x:8000`)로 변경하세요.
  (PC와 휴대폰이 같은 Wi-Fi에 연결되어 있어야 합니다.)

## 4. 실행

```bash
# 백엔드가 먼저 실행 중이어야 합니다 (../backend 참고)
flutter run
```

## 참고: Android APK 빌드 시 JDK 버전 문제

Java 25 이상의 JDK만 설치된 환경(예: 최신 Android Studio 번들 JBR만 있는 경우)에서는
`flutter build apk` / Android 빌드가 실패합니다.

- Gradle 7.x/8.x대는 Java 25를 지원하지 않아 `Unsupported class file major version 69` 에러가 납니다.
- Java 25를 지원하는 Gradle 9.x로 올리면, 이번에는 Flutter 3.22.2에 내장된 Gradle 플러그인
  (`flutter_tools/gradle/src/main/groovy/flutter.groovy`)이 Gradle 9.x의 최신 Groovy 런타임과
  호환되지 않아 `unable to resolve class groovy.xml.QName` 에러가 납니다.

**해결: JDK 17(또는 21)을 별도 설치**하고 Flutter가 그 JDK를 사용하도록 지정하면 됩니다
(`android/gradle/wrapper/gradle-wrapper.properties`, `android/settings.gradle`은
`flutter create .`가 생성한 기본값 Gradle 7.6.3 / AGP 7.3.0 / Kotlin 1.7.10 그대로 두면 됩니다):

```bash
# Homebrew가 없다면 Adoptium에서 직접 다운로드
curl -L -o jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse?project=jdk"
tar -xzf jdk17.tar.gz

flutter config --jdk-dir="$(pwd)/jdk-17.x.x+y/Contents/Home"
flutter build apk --debug
```

이 방법으로 실제 macOS 13.2 + Java 25 환경에서도 APK 빌드 및 실기기(Android 16) 설치·실행까지
검증했습니다. 최초 빌드는 Gradle/빌드도구 다운로드로 몇 분 걸리지만 이후 빌드는 수 초면 끝납니다.

Dart 코드 자체는 `flutter analyze`(이슈 없음) · `flutter test`(통과) · `flutter build web --release` ·
실기기 APK 실행까지 전부 검증되었습니다.

## 주요 화면 구성

- **홈**: 오늘의 요약, 빠른 실행(농장 등록/작업 기록/AI 진단), 농자재사 처방 알림 수신함
- **농장**: 농장 등록/수정 (지번, 면적(평/㎡ 자동환산), 시설구분, 연차)
- **영농일지**: 작업 기록 등록(사진, 날짜 자동입력, 작업면적 자동입력), 목록/캘린더 뷰 전환
- **AI진단**: 사진 업로드 → EXIF GPS/촬영일시 추출 → OpenWeather 기상 조회 → Gemini 진단 → 친환경 자재 최우선 추천
- **통계**: 유형별/월별/TOP5 차트, AI 예측 정확도, 농장별 PDF 리포트 다운로드
