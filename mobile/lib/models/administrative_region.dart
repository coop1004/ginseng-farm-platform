class AdministrativeRegion {
  final int id;
  final String sido;
  final String sigungu;

  AdministrativeRegion({required this.id, required this.sido, required this.sigungu});

  factory AdministrativeRegion.fromJson(Map<String, dynamic> json) {
    return AdministrativeRegion(
      id: json['id'],
      sido: json['sido'] ?? '',
      sigungu: json['sigungu'] ?? '',
    );
  }
}
