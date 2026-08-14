class WeatherRecord {
  final int id;
  final int farmId;
  final String? farmName;
  final DateTime recordDate;
  final double? tempC;
  final double? humidityPercent;
  final double? rainfallMm;
  final double? windMs;
  final String? source;

  WeatherRecord({
    required this.id,
    required this.farmId,
    this.farmName,
    required this.recordDate,
    this.tempC,
    this.humidityPercent,
    this.rainfallMm,
    this.windMs,
    this.source,
  });

  factory WeatherRecord.fromJson(Map<String, dynamic> json) {
    return WeatherRecord(
      id: json['id'],
      farmId: json['farm_id'],
      farmName: json['farm_name'],
      recordDate: DateTime.parse(json['record_date']),
      tempC: (json['temp_c'] as num?)?.toDouble(),
      humidityPercent: (json['humidity_percent'] as num?)?.toDouble(),
      rainfallMm: (json['rainfall_mm'] as num?)?.toDouble(),
      windMs: (json['wind_ms'] as num?)?.toDouble(),
      source: json['source'],
    );
  }
}
