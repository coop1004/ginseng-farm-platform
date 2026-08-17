import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/administrative_region.dart';
import '../models/app_notification.dart';
import '../models/auth.dart';
import '../models/community.dart';
import '../models/crop.dart';
import '../models/diagnosis.dart';
import '../models/farm.dart';
import '../models/pest_reference.dart';
import '../models/stats.dart';
import '../models/weather_record.dart';
import '../models/work_log.dart';
import 'app_config.dart';
import 'auth_store.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

class UnauthorizedException implements Exception {
  @override
  String toString() => '로그인이 만료되었습니다. 다시 로그인해주세요.';
}

class ApiService {
  Future<String> get _base async => AppConfig.getBaseUrl();

  Future<Uri> _uri(String path, [Map<String, dynamic>? query]) async {
    final base = await _base;
    final qp = <String, String>{};
    query?.forEach((k, v) {
      if (v != null) qp[k] = v.toString();
    });
    return Uri.parse('$base$path').replace(queryParameters: qp.isEmpty ? null : qp);
  }

  Future<Map<String, String>> _authHeaders({bool json = false}) async {
    final token = await AuthStore.getToken();
    return {
      if (json) 'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  void _checkResponse(http.Response res) {
    if (res.statusCode == 401) {
      throw UnauthorizedException();
    }
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException('서버 오류 (${res.statusCode}): ${res.body}');
    }
  }

  Future<String> photoUrlAsync(String? photoPath) async {
    if (photoPath == null || photoPath.isEmpty) return '';
    final base = await _base;
    return '$base/uploads/$photoPath';
  }

  /// 사진 업로드(MultipartRequest)는 시골 현장 등 통신이 불안정한 곳에서 실패하기
  /// 쉬운데, 지금까지는 실패하면 바로 사용자에게 에러만 보여주고 입력한 내용과
  /// 사진이 그대로 사라졌다. 네트워크 순간 끊김 정도는 자동으로 복구되도록,
  /// MultipartRequest를 매 시도마다 새로 만들어서(한 번 보낸 요청은 재사용 불가)
  /// 지수 백오프로 재시도한다. 서버가 명확히 거부한 4xx는 재시도해도 결과가
  /// 같으므로 재시도하지 않고 바로 반환한다.
  Future<http.Response> _sendMultipartWithRetry(
    Future<http.MultipartRequest> Function() buildRequest, {
    int maxAttempts = 3,
  }) async {
    Object lastError = ApiException('알 수 없는 오류');
    for (var attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        final request = await buildRequest();
        final streamed = await request.send().timeout(const Duration(seconds: 30));
        final res = await http.Response.fromStream(streamed);
        if (res.statusCode < 500) return res; // 성공 또는 4xx(재시도해도 동일) -> 그대로 반환
        lastError = ApiException('서버 오류 (${res.statusCode}): ${res.body}');
      } catch (e) {
        lastError = e;
      }
      if (attempt < maxAttempts) {
        await Future.delayed(Duration(seconds: attempt * 2)); // 2초, 4초 대기 후 재시도
      }
    }
    throw ApiException('네트워크 연결이 불안정합니다. 잠시 후 다시 시도해주세요. ($lastError)');
  }

  // ---------- Auth ----------
  Future<TokenResponse> registerNewHousehold({
    required String phone,
    required String password,
    required String name,
    required String householdName,
    List<int> cropIds = const [],
  }) async {
    final res = await http.post(
      await _uri('/api/auth/register/new-household'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'password': password,
        'name': name,
        'household_name': householdName,
        'crop_ids': cropIds,
      }),
    );
    _checkResponse(res);
    return TokenResponse.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<TokenResponse> registerJoinHousehold({
    required String phone,
    required String password,
    required String name,
    required String joinCode,
  }) async {
    final res = await http.post(
      await _uri('/api/auth/register/join-household'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'password': password,
        'name': name,
        'join_code': joinCode,
      }),
    );
    _checkResponse(res);
    return TokenResponse.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<TokenResponse> login({required String phone, required String password}) async {
    final res = await http.post(
      await _uri('/api/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'phone': phone, 'password': password}),
    );
    _checkResponse(res);
    return TokenResponse.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<MeResponse> me() async {
    final res = await http.get(await _uri('/api/auth/me'), headers: await _authHeaders());
    _checkResponse(res);
    return MeResponse.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  // ---------- Farms ----------
  Future<List<Farm>> getFarms() async {
    final res = await http.get(await _uri('/api/farms'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => Farm.fromJson(e)).toList();
  }

  Future<Farm> createFarm(Farm farm) async {
    final res = await http.post(
      await _uri('/api/farms'),
      headers: await _authHeaders(json: true),
      body: jsonEncode(farm.toJson()),
    );
    _checkResponse(res);
    return Farm.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<Farm> updateFarm(int id, Farm farm) async {
    final res = await http.put(
      await _uri('/api/farms/$id'),
      headers: await _authHeaders(json: true),
      body: jsonEncode(farm.toJson()),
    );
    _checkResponse(res);
    return Farm.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<void> deleteFarm(int id) async {
    final res = await http.delete(await _uri('/api/farms/$id'), headers: await _authHeaders());
    _checkResponse(res);
  }

  /// 지역 위험 신호등 등급("주의"/"경계") 또는 null(신호 없음). 병해충명·건수는 서버에서부터
  /// 응답에 포함되지 않는다(프라이버시 - 이웃 농가를 식별할 수 있는 정보이기 때문).
  Future<String?> getRegionalRiskSignal(int farmId) async {
    final res = await http.get(await _uri('/api/farms/$farmId/regional-risk-signal'), headers: await _authHeaders());
    _checkResponse(res);
    final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    return data['level'] as String?;
  }

  // ---------- Crops ----------
  Future<List<Crop>> getCrops() async {
    final res = await http.get(await _uri('/api/crops'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => Crop.fromJson(e)).toList();
  }

  Future<List<GrowthStage>> getGrowthStages(int cropId) async {
    final res = await http.get(await _uri('/api/crops/$cropId/growth-stages'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => GrowthStage.fromJson(e)).toList();
  }

  // ---------- Regions ----------
  Future<List<AdministrativeRegion>> getRegions() async {
    final res = await http.get(await _uri('/api/regions'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => AdministrativeRegion.fromJson(e)).toList();
  }

  Future<List<PestReference>> getPestReferences({int? cropId}) async {
    final res = await http.get(await _uri('/api/reference', {'crop_id': cropId}), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => PestReference.fromJson(e)).toList();
  }

  // ---------- Work Logs ----------
  Future<List<WorkLog>> getWorkLogs({int? farmId, DateTime? start, DateTime? end}) async {
    final res = await http.get(
      await _uri('/api/work-logs', {
        'farm_id': farmId,
        'start_date': start != null ? _dateStr(start) : null,
        'end_date': end != null ? _dateStr(end) : null,
      }),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => WorkLog.fromJson(e)).toList();
  }

  Future<WorkLog> createWorkLog({
    required int farmId,
    required DateTime workDate,
    required double workAreaM2,
    required String content,
    File? photo,
  }) async {
    final res = await _sendMultipartWithRetry(() async {
      final uri = await _uri('/api/work-logs');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(await _authHeaders())
        ..fields['farm_id'] = farmId.toString()
        ..fields['work_date'] = _dateStr(workDate)
        ..fields['work_area_m2'] = workAreaM2.toString()
        ..fields['content'] = content;
      if (photo != null) {
        request.files.add(await http.MultipartFile.fromPath('photo', photo.path));
      }
      return request;
    });
    _checkResponse(res);
    return WorkLog.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  // ---------- Diagnosis ----------
  Future<List<Diagnosis>> getDiagnoses({
    int? farmId,
    String? diagnosisType,
    DateTime? start,
    DateTime? end,
  }) async {
    final res = await http.get(
      await _uri('/api/diagnoses', {
        'farm_id': farmId,
        'diagnosis_type': diagnosisType,
        'start_date': start != null ? _dateStr(start) : null,
        'end_date': end != null ? _dateStr(end) : null,
      }),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => Diagnosis.fromJson(e)).toList();
  }

  Future<Diagnosis> submitDiagnosisFeedback({required int diagnosisId, required bool correct}) async {
    final res = await http.patch(
      await _uri('/api/diagnoses/$diagnosisId/feedback'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'correct': correct}),
    );
    _checkResponse(res);
    return Diagnosis.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<Diagnosis> createDiagnosis({
    required int farmId,
    required String diagnosisType,
    required String cropName,
    required List<File> photos,
    DateTime? occurrenceDate,
  }) async {
    final res = await _sendMultipartWithRetry(() async {
      final uri = await _uri('/api/diagnoses');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(await _authHeaders())
        ..fields['farm_id'] = farmId.toString()
        ..fields['diagnosis_type'] = diagnosisType
        ..fields['crop_name'] = cropName;
      // 사용자가 직접 고른 날짜가 있을 때만 보낸다 - 안 보내면 서버가 사진 EXIF
      // 촬영일(있으면)이나 오늘 날짜로 알아서 채운다(diagnosis_service.py).
      // 항상 오늘 날짜를 보내면 그 자동 판단을 매번 덮어써버리게 된다.
      if (occurrenceDate != null) {
        final y = occurrenceDate.year.toString().padLeft(4, '0');
        final m = occurrenceDate.month.toString().padLeft(2, '0');
        final d = occurrenceDate.day.toString().padLeft(2, '0');
        request.fields['occurrence_date'] = '$y-$m-$d';
      }
      for (final photo in photos) {
        request.files.add(await http.MultipartFile.fromPath('photos', photo.path));
      }
      return request;
    });
    _checkResponse(res);
    return Diagnosis.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<Diagnosis> submitFinalDiagnosis({
    required int diagnosisId,
    required String diseaseName,
    String? note,
  }) async {
    final res = await http.patch(
      await _uri('/api/diagnoses/$diagnosisId/final-diagnosis'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'disease_name': diseaseName, 'note': note}),
    );
    _checkResponse(res);
    return Diagnosis.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<List<DiagnosisComment>> getDiagnosisComments(int diagnosisId) async {
    final res = await http.get(await _uri('/api/diagnoses/$diagnosisId/comments'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => DiagnosisComment.fromJson(e)).toList();
  }

  Future<DiagnosisComment> createDiagnosisComment({required int diagnosisId, required String body}) async {
    final res = await http.post(
      await _uri('/api/diagnoses/$diagnosisId/comments'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'body': body}),
    );
    _checkResponse(res);
    return DiagnosisComment.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  // ---------- Community ----------
  Future<List<CommunityPost>> getCommunityPosts({int? cropId, String? kind}) async {
    final res = await http.get(
      await _uri('/api/community', {'crop_id': cropId, 'kind': kind}),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => CommunityPost.fromJson(e)).toList();
  }

  Future<CommunityPost> getCommunityPost(int postId) async {
    final res = await http.get(await _uri('/api/community/$postId'), headers: await _authHeaders());
    _checkResponse(res);
    return CommunityPost.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<CommunityPost> shareDiagnosisToCommunity({
    required int diagnosisId,
    required String title,
    String? body,
    String visibility = 'public',
  }) async {
    final res = await http.post(
      await _uri('/api/community/diagnosis-share'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'diagnosis_id': diagnosisId, 'title': title, 'body': body, 'visibility': visibility}),
    );
    _checkResponse(res);
    return CommunityPost.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<CommunityComment> createCommunityComment({required int postId, required String body}) async {
    final res = await http.post(
      await _uri('/api/community/$postId/comments'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'body': body}),
    );
    _checkResponse(res);
    return CommunityComment.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<void> reportCommunityPost({required int postId, String? reason}) async {
    final res = await http.post(
      await _uri('/api/community/$postId/report'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'reason': reason}),
    );
    _checkResponse(res);
  }

  Future<void> reportCommunityComment({required int commentId, String? reason}) async {
    final res = await http.post(
      await _uri('/api/community/comments/$commentId/report'),
      headers: {...await _authHeaders(), 'Content-Type': 'application/json'},
      body: jsonEncode({'reason': reason}),
    );
    _checkResponse(res);
  }

  // ---------- Weather ----------
  Future<List<WeatherRecord>> getWeatherHistory({int? farmId, int days = 30}) async {
    final res = await http.get(
      await _uri('/api/weather/history', {'farm_id': farmId, 'days': days}),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => WeatherRecord.fromJson(e)).toList();
  }

  // ---------- Stats ----------
  Future<StatsSummary> getStatsSummary({int? farmId, int? cropId}) async {
    final res = await http.get(
      await _uri('/api/stats/summary', {'farm_id': farmId, 'crop_id': cropId}),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    return StatsSummary.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<List<Map<String, dynamic>>> getCalendar({int? farmId, required int year, required int month}) async {
    final res = await http.get(
      await _uri('/api/stats/calendar', {'farm_id': farmId, 'year': year, 'month': month}),
      headers: await _authHeaders(),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.cast<Map<String, dynamic>>();
  }

  // ---------- Notifications (농자재사 처방 알림 수신함, 내 농가 것만) ----------
  Future<List<AppNotification>> getNotifications() async {
    final res = await http.get(await _uri('/api/notifications'), headers: await _authHeaders());
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => AppNotification.fromJson(e)).toList();
  }

  // ---------- Report ----------
  Future<String> getFarmReportPdfUrl(int farmId, DateTime start, DateTime end) async {
    final base = await _base;
    final token = await AuthStore.getToken();
    return '$base/api/reports/farms/$farmId/pdf?start_date=${_dateStr(start)}&end_date=${_dateStr(end)}'
        '${token != null ? '&token=$token' : ''}';
  }

  Future<String> getMyDataExportUrl() async {
    final base = await _base;
    final token = await AuthStore.getToken();
    return '$base/api/reports/my-data/export${token != null ? '?token=$token' : ''}';
  }

  String _dateStr(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
