class AuthUser {
  final int id;
  final String phone;
  final String name;

  AuthUser({required this.id, required this.phone, required this.name});

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(id: json['id'], phone: json['phone'] ?? '', name: json['name'] ?? '');
  }
}

class HouseholdInfo {
  final int id;
  final String name;
  final String joinCode;

  HouseholdInfo({required this.id, required this.name, required this.joinCode});

  factory HouseholdInfo.fromJson(Map<String, dynamic> json) {
    return HouseholdInfo(id: json['id'], name: json['name'] ?? '', joinCode: json['join_code'] ?? '');
  }
}

class TokenResponse {
  final String accessToken;
  final AuthUser user;
  final HouseholdInfo household;

  TokenResponse({required this.accessToken, required this.user, required this.household});

  factory TokenResponse.fromJson(Map<String, dynamic> json) {
    return TokenResponse(
      accessToken: json['access_token'],
      user: AuthUser.fromJson(json['user']),
      household: HouseholdInfo.fromJson(json['household']),
    );
  }
}

class MeResponse {
  final AuthUser user;
  final HouseholdInfo household;
  final List<AuthUser> members;

  MeResponse({required this.user, required this.household, required this.members});

  factory MeResponse.fromJson(Map<String, dynamic> json) {
    return MeResponse(
      user: AuthUser.fromJson(json['user']),
      household: HouseholdInfo.fromJson(json['household']),
      members: (json['members'] as List<dynamic>? ?? []).map((e) => AuthUser.fromJson(e)).toList(),
    );
  }
}
