class Farm {
  final int id;
  final int householdId;
  final String? householdName;
  final String farmName;
  final String address;
  final String? region;
  final double? latitude;
  final double? longitude;
  final double areaPyeong;
  final double areaM2;
  final String facilityType;
  final int cultivationYear;
  final String? phone;
  final String? memo;
  final DateTime createdAt;

  Farm({
    required this.id,
    required this.householdId,
    this.householdName,
    required this.farmName,
    required this.address,
    this.region,
    this.latitude,
    this.longitude,
    required this.areaPyeong,
    required this.areaM2,
    required this.facilityType,
    required this.cultivationYear,
    this.phone,
    this.memo,
    required this.createdAt,
  });

  factory Farm.fromJson(Map<String, dynamic> json) {
    return Farm(
      id: json['id'],
      householdId: json['household_id'] ?? 0,
      householdName: json['household_name'],
      farmName: json['farm_name'] ?? '',
      address: json['address'] ?? '',
      region: json['region'],
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      areaPyeong: (json['area_pyeong'] as num?)?.toDouble() ?? 0,
      areaM2: (json['area_m2'] as num?)?.toDouble() ?? 0,
      facilityType: json['facility_type'] ?? '노지',
      cultivationYear: json['cultivation_year'] ?? 1,
      phone: json['phone'],
      memo: json['memo'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'farm_name': farmName,
      'address': address,
      'region': region,
      'latitude': latitude,
      'longitude': longitude,
      'area_pyeong': areaPyeong,
      'area_m2': areaM2,
      'facility_type': facilityType,
      'cultivation_year': cultivationYear,
      'phone': phone,
      'memo': memo,
    };
  }
}

const facilityTypes = ['노지', '해가림', '스마트팜'];
