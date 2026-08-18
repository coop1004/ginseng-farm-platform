import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:table_calendar/table_calendar.dart';

import '../models/farm.dart';
import '../models/work_log.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'work_log_form_screen.dart';

class WorkLogScreen extends StatefulWidget {
  const WorkLogScreen({super.key});

  @override
  State<WorkLogScreen> createState() => _WorkLogScreenState();
}

class _WorkLogScreenState extends State<WorkLogScreen> {
  final _api = ApiService();
  bool _calendarMode = false;
  Farm? _filterFarm;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;

  List<WorkLog> _logs = [];
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
      final logs = await _api.getWorkLogs(farmId: _filterFarm?.id);
      setState(() => _logs = logs);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  Map<DateTime, List<WorkLog>> get _byDay {
    final map = <DateTime, List<WorkLog>>{};
    for (final log in _logs) {
      final key = DateTime(log.workDate.year, log.workDate.month, log.workDate.day);
      map.putIfAbsent(key, () => []).add(log);
    }
    return map;
  }

  @override
  Widget build(BuildContext context) {
    final farms = context.watch<FarmProvider>().farms;
    final visibleLogs = _selectedDay == null
        ? _logs
        : _logs.where((l) =>
            l.workDate.year == _selectedDay!.year &&
            l.workDate.month == _selectedDay!.month &&
            l.workDate.day == _selectedDay!.day).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('영농일지'),
        actions: [
          IconButton(
            icon: Icon(_calendarMode ? Icons.view_list : Icons.calendar_month),
            tooltip: _calendarMode ? '목록 보기' : '캘린더 보기',
            onPressed: () => setState(() => _calendarMode = !_calendarMode),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final created = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const WorkLogFormScreen()),
          );
          if (created == true) _load();
        },
        icon: const Icon(Icons.add),
        label: const Text('작업 기록'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: DropdownButtonFormField<int?>(
              value: _filterFarm?.id,
              isExpanded: true,
              decoration: const InputDecoration(labelText: '농장 필터', prefixIcon: Icon(Icons.filter_alt_outlined)),
              items: [
                const DropdownMenuItem<int?>(value: null, child: Text('전체 농장')),
                ...farms.map((f) => DropdownMenuItem<int?>(
                    value: f.id, child: Text(f.farmName, overflow: TextOverflow.ellipsis, maxLines: 1))),
              ],
              onChanged: (id) {
                setState(() => _filterFarm = id == null ? null : farms.firstWhere((f) => f.id == id));
                _load();
              },
            ),
          ),
          if (_calendarMode)
            Card(
              margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: TableCalendar<WorkLog>(
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
                  markerDecoration: BoxDecoration(color: Color(0xFF2E7D32), shape: BoxShape.circle),
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
                      ? ErrorView(message: '작업일지를 불러오지 못했습니다.\n$_error', onRetry: _load)
                      : visibleLogs.isEmpty
                          ? const EmptyView(message: '작업 기록이 없습니다.', icon: Icons.edit_note_outlined)
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 12, 16, 90),
                              itemCount: visibleLogs.length,
                              itemBuilder: (context, i) => _WorkLogCard(log: visibleLogs[i]),
                            ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WorkLogCard extends StatelessWidget {
  final WorkLog log;
  const _WorkLogCard({required this.log});

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('yyyy.MM.dd (E)', 'ko_KR').format(log.workDate);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 6,
              height: 46,
              decoration: BoxDecoration(color: Colors.green.shade400, borderRadius: BorderRadius.circular(4)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(dateStr, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5)),
                      const Spacer(),
                      if (log.farmName != null)
                        Text(log.farmName!, style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(log.content, style: const TextStyle(fontSize: 13.5)),
                  const SizedBox(height: 4),
                  Text('작업면적 ${log.workAreaM2.toStringAsFixed(0)}㎡',
                      style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
