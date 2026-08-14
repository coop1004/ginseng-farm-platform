import 'diagnosis.dart';

class PestReference {
  final int id;
  final int? cropId;
  final String cropName;
  final String type; // 병해 / 해충 / 생리장애
  final String nameKr;
  final String? nameEn;
  final String? symptoms;
  final String? cause;
  final String? photoPath;
  final bool isSampleData;
  final List<TreatmentItem> ecoTreatments;
  final List<TreatmentItem> chemicalTreatments;

  PestReference({
    required this.id,
    this.cropId,
    required this.cropName,
    required this.type,
    required this.nameKr,
    this.nameEn,
    this.symptoms,
    this.cause,
    this.photoPath,
    required this.isSampleData,
    required this.ecoTreatments,
    required this.chemicalTreatments,
  });

  factory PestReference.fromJson(Map<String, dynamic> json) {
    return PestReference(
      id: json['id'],
      cropId: json['crop_id'],
      cropName: json['crop_name'] ?? '',
      type: json['type'] ?? '',
      nameKr: json['name_kr'] ?? '',
      nameEn: json['name_en'],
      symptoms: json['symptoms'],
      cause: json['cause'],
      photoPath: json['photo_path'],
      isSampleData: json['is_sample_data'] ?? false,
      ecoTreatments: (json['eco_treatments'] as List<dynamic>? ?? []).map((e) => TreatmentItem.fromJson(e)).toList(),
      chemicalTreatments:
          (json['chemical_treatments'] as List<dynamic>? ?? []).map((e) => TreatmentItem.fromJson(e)).toList(),
    );
  }
}
