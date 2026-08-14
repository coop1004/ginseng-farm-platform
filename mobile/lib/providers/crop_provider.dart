import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/auth.dart';
import '../models/crop.dart';

/// 로그인한 농가가 등록한 작물 범위와, 화면에서 현재 보고 있는 "활성 작물"을 관리한다.
/// 등록 작물이 1개뿐이면(기존 인삼 단일 작물 농가 전부 해당) activeCrop은 그 하나로
/// 고정되고, 화면 어디에도 작물 선택/전환 UI가 나타나지 않는다 — 예전과 동일한 경험.
class CropProvider extends ChangeNotifier {
  static const _prefKey = 'active_crop_id';

  List<Crop> myCrops = [];
  Crop? activeCrop;

  bool get hasMultipleCrops => myCrops.length > 1;

  Future<void> loadFromHousehold(HouseholdInfo? household) async {
    myCrops = household?.crops ?? [];
    if (myCrops.isEmpty) {
      activeCrop = null;
      notifyListeners();
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getInt(_prefKey);
    Crop? saved;
    for (final c in myCrops) {
      if (c.id == savedId) {
        saved = c;
        break;
      }
    }
    activeCrop = saved ?? myCrops.first;
    notifyListeners();
  }

  Future<void> setActiveCrop(Crop crop) async {
    activeCrop = crop;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_prefKey, crop.id);
  }

  Future<void> clear() async {
    myCrops = [];
    activeCrop = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefKey);
    notifyListeners();
  }
}
