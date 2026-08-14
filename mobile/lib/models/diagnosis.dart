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
  final DateTime createdAt;

  Diagnosis({
    required this.id,
    required this.farmId,
    this.farmName,
    required this.diagnosisType,
    required this.cropName,
    required this.occurrenceDate,
    this.photoPath,
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
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

const diagnosisTypes = ['병해', '해충', '생리장애'];
