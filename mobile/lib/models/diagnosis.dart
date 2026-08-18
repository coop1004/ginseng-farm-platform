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

/// 진단 1건의 사진 타임라인 항목 - phase="initial"(등록 시점 사진) 또는
/// phase="followup"(방제 경과 기록, 사진 없이 자가평가만 있을 수도 있음).
class DiagnosisPhotoEntry {
  final int id;
  final String phase;
  final String? photoPath;
  final String? outcome; // 호전 / 유지 / 악화 (followup만)
  final String? note;
  final int? daysSinceTreatment;
  final DateTime createdAt;

  DiagnosisPhotoEntry({
    required this.id,
    required this.phase,
    this.photoPath,
    this.outcome,
    this.note,
    this.daysSinceTreatment,
    required this.createdAt,
  });

  factory DiagnosisPhotoEntry.fromJson(Map<String, dynamic> json) {
    return DiagnosisPhotoEntry(
      id: json['id'],
      phase: json['phase'] ?? 'initial',
      photoPath: json['photo_path'],
      outcome: json['outcome'],
      note: json['note'],
      daysSinceTreatment: json['days_since_treatment'] as int?,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

/// 새 진단 등록 폼 진입 시 "이어서 기록하시겠습니까?" 후보로 보여줄 최근 미해결 진단.
class RecentUnresolvedDiagnosis {
  final int id;
  final String diagnosisType;
  final String? diseaseName;
  final DateTime occurrenceDate;
  final DateTime lastActivityAt;

  RecentUnresolvedDiagnosis({
    required this.id,
    required this.diagnosisType,
    this.diseaseName,
    required this.occurrenceDate,
    required this.lastActivityAt,
  });

  factory RecentUnresolvedDiagnosis.fromJson(Map<String, dynamic> json) {
    return RecentUnresolvedDiagnosis(
      id: json['id'],
      diagnosisType: json['diagnosis_type'] ?? '',
      diseaseName: json['disease_name'],
      occurrenceDate: DateTime.parse(json['occurrence_date']),
      lastActivityAt: DateTime.parse(json['last_activity_at']),
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
  final bool gpsEstimated;
  final DateTime? photoTakenAt;
  final bool photoTakenAtEstimated;

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

  final List<DiagnosisPhotoEntry> photoTimeline;
  final String? latestFollowupOutcome;

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
    this.gpsEstimated = false,
    this.photoTakenAt,
    this.photoTakenAtEstimated = false,
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
    this.photoTimeline = const [],
    this.latestFollowupOutcome,
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
      gpsEstimated: json['gps_estimated'] ?? false,
      photoTakenAt: json['photo_taken_at'] != null ? DateTime.tryParse(json['photo_taken_at']) : null,
      photoTakenAtEstimated: json['photo_taken_at_estimated'] ?? false,
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
      photoTimeline: (json['photo_timeline'] as List<dynamic>? ?? [])
          .map((e) => DiagnosisPhotoEntry.fromJson(e))
          .toList(),
      latestFollowupOutcome: json['latest_followup_outcome'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

class DiagnosisComment {
  final int id;
  final int diagnosisId;
  final String authorType; // household / consultant
  final String authorName;
  final String body;
  final DateTime createdAt;

  DiagnosisComment({
    required this.id,
    required this.diagnosisId,
    required this.authorType,
    required this.authorName,
    required this.body,
    required this.createdAt,
  });

  factory DiagnosisComment.fromJson(Map<String, dynamic> json) {
    return DiagnosisComment(
      id: json['id'],
      diagnosisId: json['diagnosis_id'],
      authorType: json['author_type'] ?? 'household',
      authorName: json['author_name'] ?? '',
      body: json['body'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

const diagnosisTypes = ['병해', '해충', '생리장애'];
