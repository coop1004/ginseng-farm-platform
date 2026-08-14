class TreatmentItem {
  final String productName;
  final String activeIngredient;
  final String usage;
  final String? note;

  TreatmentItem({
    required this.productName,
    required this.activeIngredient,
    required this.usage,
    this.note,
  });

  factory TreatmentItem.fromJson(Map<String, dynamic> json) {
    return TreatmentItem(
      productName: json['product_name'] ?? '',
      activeIngredient: json['active_ingredient'] ?? '',
      usage: json['usage'] ?? '',
      note: json['note'],
    );
  }
}

class Diagnosis {
  final int id;
  final int farmId;
  final String? farmName;
  final String diagnosisType; // 병해 / 해충 / 생리장애
  final String cropName;
  final DateTime occurrenceDate;
  final String? photoPath;
  final List<String> photoPaths;

  final double? gpsLat;
  final double? gpsLng;
  final DateTime? photoTakenAt;

  final double? weatherTempC;
  final double? weatherHumidityPercent;
  final double? weatherRainfallMm;
  final double? weatherWindMs;
  final String? weatherSource;

  final String? aiDiseaseName;
  final String? aiDiseaseNameEn;
  final String? aiSymptoms;
  final double? aiConfidence;
  final List<TreatmentItem> ecoTreatments;
  final List<TreatmentItem> chemicalTreatments;
  final String? aiSource;

  final String status;
  final bool? farmerConfirmedCorrect;

  final String? finalDiseaseName;
  final String? finalDiagnosisSource; // farmer / expert
  final String? finalDiagnosisNote;
  final String? finalDiagnosisBy;
  final DateTime? finalDiagnosisAt;

  final bool cropIsSampleData;

  final DateTime createdAt;

  /// 사람이 확인/정정한 최종 진단명이 있으면 그걸, 없으면 AI 진단명을 표시용으로 사용.
  String? get effectiveDiseaseName => finalDiseaseName ?? aiDiseaseName;

  Diagnosis({
    required this.id,
    required this.farmId,
    this.farmName,
    required this.diagnosisType,
    required this.cropName,
    required this.occurrenceDate,
    this.photoPath,
    this.photoPaths = const [],
    this.gpsLat,
    this.gpsLng,
    this.photoTakenAt,
    this.weatherTempC,
    this.weatherHumidityPercent,
    this.weatherRainfallMm,
    this.weatherWindMs,
    this.weatherSource,
    this.aiDiseaseName,
    this.aiDiseaseNameEn,
    this.aiSymptoms,
    this.aiConfidence,
    required this.ecoTreatments,
    required this.chemicalTreatments,
    this.aiSource,
    required this.status,
    this.farmerConfirmedCorrect,
    this.finalDiseaseName,
    this.finalDiagnosisSource,
    this.finalDiagnosisNote,
    this.finalDiagnosisBy,
    this.finalDiagnosisAt,
    this.cropIsSampleData = false,
    required this.createdAt,
  });

  factory Diagnosis.fromJson(Map<String, dynamic> json) {
    return Diagnosis(
      id: json['id'],
      farmId: json['farm_id'],
      farmName: json['farm_name'],
      diagnosisType: json['diagnosis_type'] ?? '',
      cropName: json['crop_name'] ?? '인삼',
      occurrenceDate: DateTime.parse(json['occurrence_date']),
      photoPath: json['photo_path'],
      photoPaths: (json['photo_paths'] as List<dynamic>? ?? []).map((e) => e as String).toList(),
      gpsLat: (json['gps_lat'] as num?)?.toDouble(),
      gpsLng: (json['gps_lng'] as num?)?.toDouble(),
      photoTakenAt: json['photo_taken_at'] != null ? DateTime.tryParse(json['photo_taken_at']) : null,
      weatherTempC: (json['weather_temp_c'] as num?)?.toDouble(),
      weatherHumidityPercent: (json['weather_humidity_percent'] as num?)?.toDouble(),
      weatherRainfallMm: (json['weather_rainfall_mm'] as num?)?.toDouble(),
      weatherWindMs: (json['weather_wind_ms'] as num?)?.toDouble(),
      weatherSource: json['weather_source'],
      aiDiseaseName: json['ai_disease_name'],
      aiDiseaseNameEn: json['ai_disease_name_en'],
      aiSymptoms: json['ai_symptoms'],
      aiConfidence: (json['ai_confidence'] as num?)?.toDouble(),
      ecoTreatments: (json['eco_treatments'] as List<dynamic>? ?? [])
          .map((e) => TreatmentItem.fromJson(e))
          .toList(),
      chemicalTreatments: (json['chemical_treatments'] as List<dynamic>? ?? [])
          .map((e) => TreatmentItem.fromJson(e))
          .toList(),
      aiSource: json['ai_source'],
      status: json['status'] ?? '',
      farmerConfirmedCorrect: json['farmer_confirmed_correct'] as bool?,
      finalDiseaseName: json['final_disease_name'],
      finalDiagnosisSource: json['final_diagnosis_source'],
      finalDiagnosisNote: json['final_diagnosis_note'],
      finalDiagnosisBy: json['final_diagnosis_by'],
      finalDiagnosisAt: json['final_diagnosis_at'] != null ? DateTime.tryParse(json['final_diagnosis_at']) : null,
      cropIsSampleData: json['crop_is_sample_data'] ?? false,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

const diagnosisTypes = ['병해', '해충', '생리장애'];
