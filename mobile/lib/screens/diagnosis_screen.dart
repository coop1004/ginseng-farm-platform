import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:table_calendar/table_calendar.dart';

import '../models/diagnosis.dart';
import '../models/farm.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'diagnosis_followup_screen.dart' show outcomeBadgeLabel, outcomeColor, outcomeIcon;
import 'diagnosis_form_screen.dart';
import 'diagnosis_result_screen.dart';

class DiagnosisScreen extends StatefulWidget {
  const DiagnosisScreen({super.key});

  @override
  State<DiagnosisScreen> createState() => _DiagnosisScreenState();
}

class _DiagnosisScreenState extends State<DiagnosisScreen> {
  final _api = ApiService();
  Farm? _filterFarm;
  String? _filterType;

  // work_log_screen.dart와 동일한 캘린더 패턴 재사용 - 농장/유형은 서버 조회 조건으로
  // 그대로 두고, 날짜 선택은 이미 불러온 목록 위에 클라이언트에서 한 번 더 거른다.
  bool _showCalendar = false;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;

  List<Diagnosis> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await _api.getDiagnoses(farmId: _filterFarm?.id, diagnosisType: _filterType);
      setState(() => _items = items);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  Map<DateTime, List<Diagnosis>> get _byDay {
    final map = <DateTime, List<Diagnosis>>{};
    for (final item in _items) {
      final key = DateTime(item.occurrenceDate.year, item.occurrenceDate.month, item.occurrenceDate.day);
      map.putIfAbsent(key, () => []).add(item);
    }
    return map;
  }

  @override
  Widget build(BuildContext context) {
    final activeCropId = context.watch<CropProvider>().activeCrop?.id;
    final farms = context.watch<FarmProvider>().forCrop(activeCropId);
    final visibleItems = _selectedDay == null
        ? _items
        : _items.where((d) =>
            d.occurrenceDate.year == _selectedDay!.year &&
            d.occurrenceDate.month == _selectedDay!.month &&
            d.occurrenceDate.day == _selectedDay!.day).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('병해충일지'),
        actions: [
          IconButton(
            icon: Icon(_showCalendar ? Icons.view_list : Icons.calendar_month),
            tooltip: _showCalendar ? '목록 보기' : '캘린더 보기',
            onPressed: () => setState(() => _showCalendar = !_showCalendar),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final created = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const DiagnosisFormScreen()),
          );
          if (created == true) _load();
        },
        icon: const Icon(Icons.add_a_photo_outlined),
        label: const Text('새 진단'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<int?>(
                    value: _filterFarm?.id,
                    isExpanded: true,
                    itemHeight: null,
                    decoration: const InputDecoration(labelText: '농장'),
                    items: [
                      const DropdownMenuItem<int?>(value: null, child: Text('전체')),
                      ...farms.map((f) => DropdownMenuItem<int?>(
                          value: f.id, child: Text(f.farmName, overflow: TextOverflow.ellipsis, maxLines: 1))),
                    ],
                    onChanged: (id) {
                      setState(() => _filterFarm = id == null ? null : farms.firstWhere((f) => f.id == id));
                      _load();
                    },
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: DropdownButtonFormField<String?>(
                    value: _filterType,
                    isExpanded: true,
                    itemHeight: null,
                    decoration: const InputDecoration(labelText: '유형'),
                    items: [
                      const DropdownMenuItem<String?>(value: null, child: Text('전체')),
                      ...diagnosisTypes.map((t) => DropdownMenuItem<String?>(value: t, child: Text(t))),
                    ],
                    onChanged: (t) {
                      setState(() => _filterType = t);
                      _load();
                    },
                  ),
                ),
              ],
            ),
          ),
          if (_showCalendar)
            Card(
              margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: TableCalendar<Diagnosis>(
                locale: 'ko_KR',
                firstDay: DateTime(2020, 1, 1),
                lastDay: DateTime(2035, 12, 31),
                focusedDay: _focusedDay,
                selectedDayPredicate: (d) => _selectedDay != null && isSameDay(d, _selectedDay),
                eventLoader: (day) => _byDay[DateTime(day.year, day.month, day.day)] ?? [],
                onDaySelected: (selected, focused) {
                  setState(() {
                    _selectedDay = isSameDay(_selectedDay, selected) ? null : selected;
                    _focusedDay = focused;
                  });
                },
                onPageChanged: (focused) => _focusedDay = focused,
                calendarStyle: const CalendarStyle(
                  markerDecoration: BoxDecoration(color: AppColors.orange, shape: BoxShape.circle),
                  todayDecoration: BoxDecoration(color: Color(0xFFA5D6A7), shape: BoxShape.circle),
                  selectedDecoration: BoxDecoration(color: Color(0xFF2E7D32), shape: BoxShape.circle),
                ),
                headerStyle: const HeaderStyle(formatButtonVisible: false, titleCentered: true),
              ),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: _loading
                  ? const LoadingView()
                  : _error != null
                      ? ErrorView(message: '진단 기록을 불러오지 못했습니다.\n$_error', onRetry: _load)
                      : visibleItems.isEmpty
                          ? EmptyView(
                              message: _selectedDay == null ? '진단 기록이 없습니다.' : '선택한 날짜에 진단 기록이 없습니다.',
                              icon: Icons.biotech_outlined)
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
                              itemCount: visibleItems.length,
                              itemBuilder: (context, i) => _DiagnosisCard(item: visibleItems[i]),
                            ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DiagnosisCard extends StatelessWidget {
  final Diagnosis item;
  const _DiagnosisCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final color = diagnosisTypeColors[item.diagnosisType] ?? Colors.grey;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => DiagnosisResultScreen(diagnosis: item)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(color: color.withOpacity(0.12), shape: BoxShape.circle),
                child: Icon(_iconFor(item.diagnosisType), color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(item.aiDiseaseName ?? '분석중',
                              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
                              overflow: TextOverflow.ellipsis),
                        ),
                        if (item.cropIsSampleData) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                                color: Colors.orange.shade50, borderRadius: BorderRadius.circular(999)),
                            child: Text('샘플',
                                style: TextStyle(fontSize: 9.5, color: Colors.orange.shade800, fontWeight: FontWeight.w700)),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${item.farmName ?? ''} · ${item.cropName} · ${DateFormat('yyyy.MM.dd').format(item.occurrenceDate)}',
                      style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary),
                    ),
                    if (item.latestFollowupOutcome != null) ...[
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: outcomeColor(item.latestFollowupOutcome!).withOpacity(0.12),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(outcomeIcon(item.latestFollowupOutcome!),
                                size: 11, color: outcomeColor(item.latestFollowupOutcome!)),
                            const SizedBox(width: 3),
                            Text(outcomeBadgeLabel(item.latestFollowupOutcome!),
                                style: TextStyle(
                                    fontSize: 10.5,
                                    color: outcomeColor(item.latestFollowupOutcome!),
                                    fontWeight: FontWeight.w700)),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (item.aiConfidence != null)
                Text('${(item.aiConfidence! * 100).toStringAsFixed(0)}%',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5, color: color)),
            ],
          ),
        ),
      ),
    );
  }

  IconData _iconFor(String type) {
    switch (type) {
      case '병해':
        return Icons.coronavirus_outlined;
      case '해충':
        return Icons.bug_report_outlined;
      default:
        return Icons.local_florist_outlined;
    }
  }
}
