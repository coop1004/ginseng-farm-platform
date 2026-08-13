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
}
