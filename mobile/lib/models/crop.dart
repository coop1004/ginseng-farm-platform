class Crop {
  final int id;
  final String nameKr;
  final String? nameEn;
  final String? iconEmoji;
  final bool isActive;
  final bool isSampleData;
  final int sortOrder;

  Crop({
    required this.id,
    required this.nameKr,
    this.nameEn,
    this.iconEmoji,
    required this.isActive,
    required this.isSampleData,
    required this.sortOrder,
  });

  factory Crop.fromJson(Map<String, dynamic> json) {
    return Crop(
      id: json['id'],
      nameKr: json['name_kr'] ?? '',
      nameEn: json['name_en'],
      iconEmoji: json['icon_emoji'],
      isActive: json['is_active'] ?? true,
      isSampleData: json['is_sample_data'] ?? false,
      sortOrder: json['sort_order'] ?? 0,
    );
  }
}

class GrowthStage {
  final int id;
  final int cropId;
  final String nameKr;
  final int sortOrder;
  final String? description;

  GrowthStage({
    required this.id,
    required this.cropId,
    required this.nameKr,
    required this.sortOrder,
    this.description,
  });

  factory GrowthStage.fromJson(Map<String, dynamic> json) {
    return GrowthStage(
      id: json['id'],
      cropId: json['crop_id'],
      nameKr: json['name_kr'] ?? '',
      sortOrder: json['sort_order'] ?? 0,
      description: json['description'],
    );
  }
}
