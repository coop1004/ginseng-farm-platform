import 'package:shared_preferences/shared_preferences.dart';

/// 로그인 토큰과 최소한의 사용자 정보를 기기에 저장/조회한다.
class AuthStore {
  static const _tokenKey = 'auth_token';
  static const _userNameKey = 'auth_user_name';
  static const _householdNameKey = 'auth_household_name';

  static String? _cachedToken;

  static Future<String?> getToken() async {
    if (_cachedToken != null) return _cachedToken;
    final prefs = await SharedPreferences.getInstance();
    _cachedToken = prefs.getString(_tokenKey);
    return _cachedToken;
  }

  static Future<void> save({
    required String token,
    required String userName,
    required String householdName,
  }) async {
    _cachedToken = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    await prefs.setString(_userNameKey, userName);
    await prefs.setString(_householdNameKey, householdName);
  }

  static Future<String?> getUserName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_userNameKey);
  }

  static Future<String?> getHouseholdName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_householdNameKey);
  }

  static Future<void> clear() async {
    _cachedToken = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_userNameKey);
    await prefs.remove(_householdNameKey);
  }
}
