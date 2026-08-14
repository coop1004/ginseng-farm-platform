import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  static const _prefKey = 'api_base_url';
  static String? _cachedBaseUrl;

  static String get defaultBaseUrl {
    // 웹(PWA)은 로컬 개발이 아니라 실제 배포된 백엔드를 기본으로 바라본다.
    // 로컬에서 flutter run -d chrome으로 개발할 땐 설정 화면에서 localhost로 바꾸면 된다.
    if (kIsWeb) return 'https://ginseng-farm-platform.onrender.com';
    if (Platform.isAndroid) return 'http://10.0.2.2:8000'; // 안드로이드 에뮬레이터에서 호스트 PC 접근용
    return 'http://localhost:8000'; // iOS 시뮬레이터 / macOS
  }

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
