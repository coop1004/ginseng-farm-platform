class WorkLog {
  final int id;
  final int farmId;
  final String? farmName;
  final DateTime workDate;
  final double workAreaM2;
  final String content;
  final String? photoPath;
  final DateTime createdAt;

  WorkLog({
    required this.id,
    required this.farmId,
    this.farmName,
    required this.workDate,
    required this.workAreaM2,
    required this.content,
    this.photoPath,
    required this.createdAt,
  });

  factory WorkLog.fromJson(Map<String, dynamic> json) {
    return WorkLog(
      id: json['id'],
      farmId: json['farm_id'],
      farmName: json['farm_name'],
      workDate: DateTime.parse(json['work_date']),
      workAreaM2: (json['work_area_m2'] as num?)?.toDouble() ?? 0,
      content: json['content'] ?? '',
      photoPath: json['photo_path'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}
