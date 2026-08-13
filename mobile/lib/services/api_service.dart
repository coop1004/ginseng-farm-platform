import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/app_notification.dart';
import '../models/diagnosis.dart';
import '../models/farm.dart';
import '../models/stats.dart';
import '../models/work_log.dart';
import 'app_config.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
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

  void _checkResponse(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException('서버 오류 (${res.statusCode}): ${res.body}');
    }
  }

  Future<String> photoUrlAsync(String? photoPath) async {
    if (photoPath == null || photoPath.isEmpty) return '';
    final base = await _base;
    return '$base/uploads/$photoPath';
  }

  // ---------- Farms ----------
  Future<List<Farm>> getFarms() async {
    final res = await http.get(await _uri('/api/farms'));
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => Farm.fromJson(e)).toList();
  }

  Future<Farm> createFarm(Farm farm) async {
    final res = await http.post(
      await _uri('/api/farms'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(farm.toJson()),
    );
    _checkResponse(res);
    return Farm.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<Farm> updateFarm(int id, Farm farm) async {
    final res = await http.put(
      await _uri('/api/farms/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(farm.toJson()),
    );
    _checkResponse(res);
    return Farm.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<void> deleteFarm(int id) async {
    final res = await http.delete(await _uri('/api/farms/$id'));
    _checkResponse(res);
  }

  // ---------- Work Logs ----------
  Future<List<WorkLog>> getWorkLogs({int? farmId, DateTime? start, DateTime? end}) async {
    final res = await http.get(await _uri('/api/work-logs', {
      'farm_id': farmId,
      'start_date': start != null ? _dateStr(start) : null,
      'end_date': end != null ? _dateStr(end) : null,
    }));
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
    final uri = await _uri('/api/work-logs');
    final request = http.MultipartRequest('POST', uri)
      ..fields['farm_id'] = farmId.toString()
      ..fields['work_date'] = _dateStr(workDate)
      ..fields['work_area_m2'] = workAreaM2.toString()
      ..fields['content'] = content;
    if (photo != null) {
      request.files.add(await http.MultipartFile.fromPath('photo', photo.path));
    }
    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
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
    final res = await http.get(await _uri('/api/diagnoses', {
      'farm_id': farmId,
      'diagnosis_type': diagnosisType,
      'start_date': start != null ? _dateStr(start) : null,
      'end_date': end != null ? _dateStr(end) : null,
    }));
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => Diagnosis.fromJson(e)).toList();
  }

  Future<Diagnosis> createDiagnosis({
    required int farmId,
    required String diagnosisType,
    required String cropName,
    required File photo,
  }) async {
    final uri = await _uri('/api/diagnoses');
    final request = http.MultipartRequest('POST', uri)
      ..fields['farm_id'] = farmId.toString()
      ..fields['diagnosis_type'] = diagnosisType
      ..fields['crop_name'] = cropName;
    request.files.add(await http.MultipartFile.fromPath('photo', photo.path));
    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
    _checkResponse(res);
    return Diagnosis.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  // ---------- Stats ----------
  Future<StatsSummary> getStatsSummary({int? farmId}) async {
    final res = await http.get(await _uri('/api/stats/summary', {'farm_id': farmId}));
    _checkResponse(res);
    return StatsSummary.fromJson(jsonDecode(utf8.decode(res.bodyBytes)));
  }

  Future<List<Map<String, dynamic>>> getCalendar({int? farmId, required int year, required int month}) async {
    final res = await http.get(
      await _uri('/api/stats/calendar', {'farm_id': farmId, 'year': year, 'month': month}),
    );
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.cast<Map<String, dynamic>>();
  }

  // ---------- Notifications (농자재사 처방 알림 수신함) ----------
  Future<List<AppNotification>> getNotifications({int? farmId}) async {
    final res = await http.get(await _uri('/api/admin/notifications', {'farm_id': farmId}));
    _checkResponse(res);
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list.map((e) => AppNotification.fromJson(e)).toList();
  }

  // ---------- Report ----------
  Future<String> getFarmReportPdfUrl(int farmId, DateTime start, DateTime end) async {
    final base = await _base;
    return '$base/api/reports/farms/$farmId/pdf?start_date=${_dateStr(start)}&end_date=${_dateStr(end)}';
  }

  String _dateStr(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
