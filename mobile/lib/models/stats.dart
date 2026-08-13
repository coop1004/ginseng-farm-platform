class TopPest {
  final String name;
  final int count;
  TopPest({required this.name, required this.count});
  factory TopPest.fromJson(Map<String, dynamic> json) =>
      TopPest(name: json['name'] ?? '', count: json['count'] ?? 0);
}

class MonthlyCount {
  final String month;
  final int count;
  MonthlyCount({required this.month, required this.count});
  factory MonthlyCount.fromJson(Map<String, dynamic> json) =>
      MonthlyCount(month: json['month'] ?? '', count: json['count'] ?? 0);
}

class FarmStatCount {
  final int farmId;
  final String farmName;
  final int count;
  FarmStatCount({required this.farmId, required this.farmName, required this.count});
  factory FarmStatCount.fromJson(Map<String, dynamic> json) => FarmStatCount(
        farmId: json['farm_id'],
        farmName: json['farm_name'] ?? '',
        count: json['count'] ?? 0,
      );
}

class StatsSummary {
  final int totalFarms;
  final int totalWorkLogs;
  final int totalDiagnoses;
  final Map<String, int> diagnosesByType;
  final List<TopPest> topPests;
  final List<MonthlyCount> monthlyDiagnoses;
  final List<FarmStatCount> diagnosesByFarm;
  final Map<String, dynamic> aiVsActual;

  StatsSummary({
    required this.totalFarms,
    required this.totalWorkLogs,
    required this.totalDiagnoses,
    required this.diagnosesByType,
    required this.topPests,
    required this.monthlyDiagnoses,
    required this.diagnosesByFarm,
    required this.aiVsActual,
  });

  factory StatsSummary.fromJson(Map<String, dynamic> json) {
    return StatsSummary(
      totalFarms: json['total_farms'] ?? 0,
      totalWorkLogs: json['total_work_logs'] ?? 0,
      totalDiagnoses: json['total_diagnoses'] ?? 0,
      diagnosesByType: Map<String, int>.from(json['diagnoses_by_type'] ?? {}),
      topPests: (json['top_pests'] as List<dynamic>? ?? []).map((e) => TopPest.fromJson(e)).toList(),
      monthlyDiagnoses: (json['monthly_diagnoses'] as List<dynamic>? ?? [])
          .map((e) => MonthlyCount.fromJson(e))
          .toList(),
      diagnosesByFarm: (json['diagnoses_by_farm'] as List<dynamic>? ?? [])
          .map((e) => FarmStatCount.fromJson(e))
          .toList(),
      aiVsActual: Map<String, dynamic>.from(json['ai_vs_actual'] ?? {}),
    );
  }
}
