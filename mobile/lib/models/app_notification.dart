class AppNotification {
  final int id;
  final int farmId;
  final String? farmName;
  final int? diagnosisId;
  final String title;
  final String message;
  final String? recommendedProduct;
  final String sentBy;
  final String status;
  final DateTime createdAt;

  AppNotification({
    required this.id,
    required this.farmId,
    this.farmName,
    this.diagnosisId,
    required this.title,
    required this.message,
    this.recommendedProduct,
    required this.sentBy,
    required this.status,
    required this.createdAt,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: json['id'],
      farmId: json['farm_id'],
      farmName: json['farm_name'],
      diagnosisId: json['diagnosis_id'],
      title: json['title'] ?? '',
      message: json['message'] ?? '',
      recommendedProduct: json['recommended_product'],
      sentBy: json['sent_by'] ?? '관리자',
      status: json['status'] ?? '발송됨',
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}
