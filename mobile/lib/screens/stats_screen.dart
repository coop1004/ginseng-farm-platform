import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/farm.dart';
import '../models/stats.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class StatsScreen extends StatefulWidget {
  const StatsScreen({super.key});

  @override
  State<StatsScreen> createState() => _StatsScreenState();
}

class _StatsScreenState extends State<StatsScreen> {
  final _api = ApiService();
  Farm? _filterFarm;
  StatsSummary? _summary;
  bool _loading = true;
  String? _error;

  DateTime _reportStart = DateTime.now().subtract(const Duration(days: 90));
  DateTime _reportEnd = DateTime.now();

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
      final s = await _api.getStatsSummary(farmId: _filterFarm?.id);
      setState(() => _summary = s);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _pickRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 1)),
      initialDateRange: DateTimeRange(start: _reportStart, end: _reportEnd),
    );
    if (range != null) setState(() { _reportStart = range.start; _reportEnd = range.end; });
  }

  Future<void> _downloadPdf() async {
    if (_filterFarm == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PDF 출력을 위해 농장을 먼저 선택해주세요.')));
      return;
    }
    final url = await _api.getFarmReportPdfUrl(_filterFarm!.id, _reportStart, _reportEnd);
    final uri = Uri.parse(url);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PDF를 열 수 없습니다.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final farms = context.watch<FarmProvider>().farms;

    return Scaffold(
      appBar: AppBar(title: const Text('통계 · 리포트')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            DropdownButtonFormField<int?>(
              value: _filterFarm?.id,
              decoration: const InputDecoration(labelText: '농장 선택 (전체 또는 개별)', prefixIcon: Icon(Icons.grass)),
              items: [
                const DropdownMenuItem<int?>(value: null, child: Text('전체 농장 통계')),
                ...farms.map((f) => DropdownMenuItem<int?>(value: f.id, child: Text(f.farmName))),
              ],
              onChanged: (id) {
                setState(() => _filterFarm = id == null ? null : farms.firstWhere((f) => f.id == id));
                _load();
              },
            ),
            const SizedBox(height: 8),
            if (_loading)
              const Padding(padding: EdgeInsets.only(top: 60), child: LoadingView())
            else if (_error != null)
              Padding(padding: const EdgeInsets.only(top: 60), child: ErrorView(message: '통계를 불러오지 못했습니다.\n$_error', onRetry: _load))
            else if (_summary != null)
              _buildStats(_summary!),
            const SizedBox(height: 24),
            _buildReportSection(),
          ],
        ),
      ),
    );
  }

  Widget _buildStats(StatsSummary s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: _statCard('농장 수', '${s.totalFarms}', Icons.grass, AppColors.green)),
            const SizedBox(width: 10),
            Expanded(child: _statCard('영농일지', '${s.totalWorkLogs}', Icons.edit_note, AppColors.blue)),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _statCard('AI 진단', '${s.totalDiagnoses}', Icons.biotech, AppColors.orange)),
            const SizedBox(width: 10),
            Expanded(
              child: _statCard(
                'AI 정확도',
                s.aiVsActual['accuracy_percent'] != null ? '${s.aiVsActual['accuracy_percent']}%' : '-',
                Icons.track_changes,
                Colors.purple,
              ),
            ),
          ],
        ),
        const SectionTitle('병해충 유형별 비율'),
        SizedBox(height: 220, child: _typePieChart(s.diagnosesByType)),
        const SectionTitle('월별 발생 추이'),
        SizedBox(height: 220, child: _monthlyLineChart(s.monthlyDiagnoses)),
        const SectionTitle('자주 발생하는 병해충 TOP 5'),
        SizedBox(height: 220, child: _topPestBarChart(s.topPests)),
        if (_filterFarm == null && s.diagnosesByFarm.isNotEmpty) ...[
          const SectionTitle('농장별 발생 건수'),
          ...s.diagnosesByFarm.map((f) => ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(f.farmName),
                trailing: Text('${f.count}건', style: const TextStyle(fontWeight: FontWeight.w700)),
              )),
        ],
        const SectionTitle('AI 예측 대비 실제 발생 비교'),
        _aiAccuracyCard(s.aiVsActual),
      ],
    );
  }

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: color, size: 19),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                  Text(label, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _typePieChart(Map<String, int> byType) {
    if (byType.isEmpty) return const EmptyView(message: '데이터가 없습니다.');
    final total = byType.values.fold<int>(0, (a, b) => a + b);
    return Row(
      children: [
        Expanded(
          child: PieChart(
            PieChartData(
              sectionsSpace: 2,
              centerSpaceRadius: 40,
              sections: byType.entries.map((e) {
                final color = diagnosisTypeColors[e.key] ?? Colors.grey;
                final pct = total == 0 ? 0 : (e.value / total * 100);
                return PieChartSectionData(
                  value: e.value.toDouble(),
                  color: color,
                  title: '${pct.toStringAsFixed(0)}%',
                  radius: 60,
                  titleStyle: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.w700),
                );
              }).toList(),
            ),
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: byType.keys.map((k) {
            final color = diagnosisTypeColors[k] ?? Colors.grey;
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                  const SizedBox(width: 6),
                  Text(k, style: const TextStyle(fontSize: 12)),
                  const SizedBox(width: 6),
                  Text('${byType[k]}건', style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
                ],
              ),
            );
          }).toList(),
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _monthlyLineChart(List<MonthlyCount> monthly) {
    if (monthly.isEmpty) return const EmptyView(message: '데이터가 없습니다.');
    return LineChart(
      LineChartData(
        gridData: const FlGridData(show: true, drawVerticalLine: false),
        titlesData: FlTitlesData(
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (v, meta) {
                final i = v.toInt();
                if (i < 0 || i >= monthly.length) return const SizedBox.shrink();
                final label = monthly[i].month.substring(5);
                return Padding(padding: const EdgeInsets.only(top: 6), child: Text(label, style: const TextStyle(fontSize: 10)));
              },
            ),
          ),
          leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 26, getTitlesWidget: (v, m) => Text('${v.toInt()}', style: const TextStyle(fontSize: 10)))),
        ),
        borderData: FlBorderData(show: false),
        lineBarsData: [
          LineChartBarData(
            spots: monthly.asMap().entries.map((e) => FlSpot(e.key.toDouble(), e.value.count.toDouble())).toList(),
            isCurved: true,
            color: AppColors.green,
            barWidth: 3,
            dotData: const FlDotData(show: true),
            belowBarData: BarAreaData(show: true, color: AppColors.green.withOpacity(0.12)),
          ),
        ],
      ),
    );
  }

  Widget _topPestBarChart(List<TopPest> pests) {
    if (pests.isEmpty) return const EmptyView(message: '데이터가 없습니다.');
    final maxVal = pests.map((p) => p.count).reduce((a, b) => a > b ? a : b).toDouble();
    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: maxVal + 1,
        gridData: const FlGridData(show: false),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 50,
              getTitlesWidget: (v, meta) {
                final i = v.toInt();
                if (i < 0 || i >= pests.length) return const SizedBox.shrink();
                final name = pests[i].name;
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(name.length > 5 ? '${name.substring(0, 5)}…' : name,
                      style: const TextStyle(fontSize: 9.5), textAlign: TextAlign.center),
                );
              },
            ),
          ),
        ),
        barGroups: pests.asMap().entries.map((e) {
          return BarChartGroupData(x: e.key, barRods: [
            BarChartRodData(toY: e.value.count.toDouble(), color: AppColors.orange, width: 18, borderRadius: BorderRadius.circular(4)),
          ]);
        }).toList(),
      ),
    );
  }

  Widget _aiAccuracyCard(Map<String, dynamic> ai) {
    final total = ai['total_feedback'] ?? 0;
    if (total == 0) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Text('아직 농가 확인 피드백 데이터가 없습니다.', style: TextStyle(color: Colors.grey.shade600, fontSize: 12.5)),
        ),
      );
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('정확도 ${ai['accuracy_percent']}%', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
            const SizedBox(height: 6),
            Text('일치 ${ai['correct']}건 · 불일치 ${ai['incorrect']}건 (총 $total건 피드백)',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: (ai['correct'] as int) / total,
                minHeight: 10,
                backgroundColor: Colors.red.shade100,
                valueColor: const AlwaysStoppedAnimation(AppColors.green),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildReportSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('농장별 영농일지 · 진단 리포트 출력', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
            const SizedBox(height: 4),
            Text('선택한 농장의 기간별 기록을 PDF로 출력합니다.', style: TextStyle(fontSize: 11.5, color: Colors.grey.shade600)),
            const SizedBox(height: 12),
            InkWell(
              onTap: _pickRange,
              child: InputDecorator(
                decoration: const InputDecoration(labelText: '기간', prefixIcon: Icon(Icons.date_range_outlined)),
                child: Text(
                  '${DateFormat('yyyy.MM.dd').format(_reportStart)} ~ ${DateFormat('yyyy.MM.dd').format(_reportEnd)}',
                ),
              ),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _downloadPdf,
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: const Text('PDF 리포트 다운로드'),
            ),
          ],
        ),
      ),
    );
  }
}
