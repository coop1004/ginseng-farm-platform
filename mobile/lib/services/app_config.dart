import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  static const _prefKey = 'api_base_url';
  static String? _cachedBaseUrl;

  static String get defaultBaseUrl {
    if (kIsWeb) return 'http://localhost:8000';
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
