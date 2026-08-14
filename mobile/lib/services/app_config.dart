import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  static const _prefKey = 'api_base_url';
  static String? _cachedBaseUrl;

  /// 실제 회원 농가에게 배포되는 앱(APK/PWA)이 기본으로 바라보는 서버.
  /// 로컬 에뮬레이터/시뮬레이터로 직접 개발·디버깅할 땐, 앱 실행 후
  /// 설정 화면에서 10.0.2.2(안드로이드 에뮬레이터) 또는 localhost(iOS 시뮬레이터)로
  /// 바꿔서 쓰면 된다. 실사용자 배포본의 기본값을 개발 편의용 주소로 두면
  /// 실기기에서 연결이 아예 안 되는 문제가 생기므로, 항상 배포된 백엔드를 기본값으로 한다.
  static String get defaultBaseUrl => 'https://ginseng-farm-platform.onrender.com';

  static Future<String> getBaseUrl() async {
    if (_cachedBaseUrl != null) return _cachedBaseUrl!;
    final prefs = await SharedPreferences.getInstance();
    _cachedBaseUrl = prefs.getString(_prefKey) ?? defaultBaseUrl;
    return _cachedBaseUrl!;
  }

  static Future<void> setBaseUrl(String url) async {
    final trimmed = url.trim().replaceAll(RegExp(r'/+$'), '');
    _cachedBaseUrl = trimmed;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefKey, trimmed);
  }
}
