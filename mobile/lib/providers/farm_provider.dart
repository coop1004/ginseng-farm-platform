import 'package:flutter/foundation.dart';

import '../models/farm.dart';
import '../services/api_service.dart';

class FarmProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  List<Farm> farms = [];
  bool isLoading = false;
  String? error;

  Farm? get defaultFarm => farms.isNotEmpty ? farms.first : null;

  Future<void> load() async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      farms = await _api.getFarms();
    } catch (e) {
      error = e.toString();
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Farm? byId(int id) {
    try {
      return farms.firstWhere((f) => f.id == id);
    } catch (_) {
      return null;
    }
  }

  /// 활성 작물(cropId)에 속한 필지만 반환한다. 등록 작물이 1개뿐인 농가는 전체 필지가
  /// 이미 같은 작물이라 필터링해도 결과가 지금과 동일하다. cropId가 null이면(작물 정보가
  /// 아직 안 채워졌거나 등록된 작물이 없는 예외 상황) 전체 목록을 그대로 반환한다.
  List<Farm> forCrop(int? cropId) {
    if (cropId == null) return farms;
    return farms.where((f) => f.cropId == cropId).toList();
  }
}
