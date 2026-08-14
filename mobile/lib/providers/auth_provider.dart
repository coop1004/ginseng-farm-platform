import 'package:flutter/foundation.dart';

import '../models/auth.dart';
import '../services/api_service.dart';
import '../services/auth_store.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  AuthStatus status = AuthStatus.unknown;
  AuthUser? user;
  HouseholdInfo? household;
  String? error;
  bool isLoading = false;

  Future<void> tryAutoLogin() async {
    final token = await AuthStore.getToken();
    if (token == null) {
      status = AuthStatus.unauthenticated;
      notifyListeners();
      return;
    }
    try {
      final me = await _api.me();
      user = me.user;
      household = me.household;
      status = AuthStatus.authenticated;
    } catch (_) {
      await AuthStore.clear();
      status = AuthStatus.unauthenticated;
    }
    notifyListeners();
  }

  Future<bool> login(String phone, String password) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final res = await _api.login(phone: phone, password: password);
      await _applyToken(res);
      return true;
    } catch (e) {
      error = _friendlyError(e);
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> registerNewHousehold({
    required String phone,
    required String password,
    required String name,
    required String householdName,
    List<int> cropIds = const [],
  }) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final res = await _api.registerNewHousehold(
        phone: phone,
        password: password,
        name: name,
        householdName: householdName,
        cropIds: cropIds,
      );
      await _applyToken(res);
      return true;
    } catch (e) {
      error = _friendlyError(e);
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> registerJoinHousehold({
    required String phone,
    required String password,
    required String name,
    required String joinCode,
  }) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final res = await _api.registerJoinHousehold(
        phone: phone,
        password: password,
        name: name,
        joinCode: joinCode,
      );
      await _applyToken(res);
      return true;
    } catch (e) {
      error = _friendlyError(e);
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _applyToken(TokenResponse res) async {
    await AuthStore.save(token: res.accessToken, userName: res.user.name, householdName: res.household.name);
    user = res.user;
    household = res.household;
    status = AuthStatus.authenticated;
  }

  Future<void> logout() async {
    await AuthStore.clear();
    user = null;
    household = null;
    status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  String _friendlyError(Object e) {
    final msg = e.toString();
    if (msg.contains('이미 가입된')) return '이미 가입된 전화번호입니다.';
    if (msg.contains('농가 코드를 찾을 수 없습니다')) return '농가 코드를 찾을 수 없습니다. 코드를 다시 확인해주세요.';
    if (msg.contains('전화번호 또는 비밀번호')) return '전화번호 또는 비밀번호가 올바르지 않습니다.';
    return '요청 중 오류가 발생했습니다: $msg';
  }
}
