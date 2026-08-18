import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/farm.dart';
import '../models/weather_record.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'farm_form_screen.dart';

class FarmListScreen extends StatefulWidget {
  const FarmListScreen({super.key});

  @override
  State<FarmListScreen> createState() => _FarmListScreenState();
}

class _FarmListScreenState extends State<FarmListScreen> {
  final _api = ApiService();
  Map<int, WeatherRecord> _weatherByFarm = {};

  @override
  void initState() {
    super.initState();
    _loadWeather();
  }

  /// 농장이 몇 개든 화면 진입 시 한 번만 호출 - 라이브 OpenWeather 호출이 아니라
  /// 매일 배치로 이미 쌓인 WeatherRecord를 읽어오는 것뿐이라 호출 한도 걱정이 없다.
  Future<void> _loadWeather() async {
    try {
      final records = await _api.getWeatherHistory(days: 1);
      final map = <int, WeatherRecord>{};
      for (final r in records) {
        map.putIfAbsent(r.farmId, () => r); // days=1 응답은 최신순 정렬이라 첫 값만 취한다
      }
      if (mounted) setState(() => _weatherByFarm = map);
    } catch (_) {
      // 날씨 카드는 부가 정보라 실패해도 농장 목록 자체는 그대로 보여준다.
    }
  }

  Future<void> _refresh() async {
    await Future.wait([context.read<FarmProvider>().load(), _loadWeather()]);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<FarmProvider>();
    final activeCropId = context.watch<CropProvider>().activeCrop?.id;
    final farms = provider.forCrop(activeCropId);

    return Scaffold(
      appBar: AppBar(title: const Text('농장 관리')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final created = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const FarmFormScreen()),
          );
          if (created == true && context.mounted) {
            context.read<FarmProvider>().load();
          }
        },
        icon: const Icon(Icons.add),
        label: const Text('농장 등록'),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: provider.isLoading && provider.farms.isEmpty
            ? const LoadingView()
            : provider.error != null && provider.farms.isEmpty
                ? ErrorView(message: '농장 목록을 불러오지 못했습니다.\n${provider.error}', onRetry: provider.load)
                : farms.isEmpty
                    ? const EmptyView(message: '등록된 농장이 없습니다.\n우측 하단 버튼으로 농장을 등록해보세요.', icon: Icons.grass_outlined)
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 90),
                        itemCount: farms.length,
                        itemBuilder: (context, i) =>
                            _FarmCard(farm: farms[i], weather: _weatherByFarm[farms[i].id]),
                      ),
      ),
    );
  }
}

class _FarmCard extends StatelessWidget {
  final Farm farm;
  final WeatherRecord? weather;
  const _FarmCard({required this.farm, this.weather});

  Future<void> _confirmAndDelete(BuildContext context) async {
    final api = ApiService();
    // 기록 개수 확인이 실패해도 삭제 자체는 진행할 수 있어야 하니, 보수적으로
    // "기록이 있을 수 있다"고 가정한 안내문으로 넘어간다.
    bool hasRecords = true;
    try {
      final diagnoses = await api.getDiagnoses(farmId: farm.id);
      final workLogs = await api.getWorkLogs(farmId: farm.id);
      hasRecords = diagnoses.isNotEmpty || workLogs.isNotEmpty;
    } catch (_) {}

    if (!context.mounted) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('농장 삭제'),
        content: Text(
          hasRecords
              ? '"${farm.farmName}"을(를) 목록에서 삭제할까요?\n이 농장의 진단·영농일지 기록은 삭제되지 않고 그대로 보존되며, 목록에서만 숨겨집니다.'
              : '"${farm.farmName}"을(를) 삭제할까요?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('취소')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('삭제')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await api.deleteFarm(farm.id);
      if (context.mounted) {
        context.read<FarmProvider>().load();
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('농장을 삭제했습니다.')));
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('삭제 실패: $e')));
      }
    }
  }

  Future<void> _openEdit(BuildContext context) async {
    final updated = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => FarmFormScreen(farm: farm)),
    );
    if (updated == true && context.mounted) {
      context.read<FarmProvider>().load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final isGinseng = farm.cropName == '인삼';
    final daysSinceStart =
        farm.cultivationStartDate != null ? DateTime.now().difference(farm.cultivationStartDate!).inDays : null;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _openEdit(context),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(farm.farmName,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                  ),
                  _tag(farm.facilityType, Colors.green),
                  if (isGinseng) ...[
                    const SizedBox(width: 6),
                    _tag('재배 ${farm.cultivationYearComputed}년차', Colors.orange),
                  ],
                  IconButton(
                    icon: const Icon(Icons.delete_outline, size: 20, color: AppColors.textSecondary),
                    tooltip: '농장 삭제',
                    onPressed: () => _confirmAndDelete(context),
                  ),
                ],
              ),
              const SizedBox(height: 2),
              Text(farm.address, style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
              const SizedBox(height: 4),
              Text('면적 ${farm.areaPyeong.toStringAsFixed(0)}평 (${farm.areaM2.toStringAsFixed(0)}㎡)',
                  style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
              if (isGinseng && (daysSinceStart != null || weather != null)) ...[
                const SizedBox(height: 6),
                Text(
                  [
                    if (daysSinceStart != null) '정식 $daysSinceStart일째',
                    if (weather?.tempC != null) '기온 ${weather!.tempC!.toStringAsFixed(1)}℃',
                    if (weather?.humidityPercent != null) '습도 ${weather!.humidityPercent!.toStringAsFixed(0)}%',
                    if (weather?.rainfallMm != null) '강수량 ${weather!.rainfallMm!.toStringAsFixed(1)}mm',
                  ].join(' · '),
                  style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary),
                ),
              ],
              if (isGinseng && farm.cultivationStartDateEstimated) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Icon(Icons.info_outline, size: 13, color: Colors.orange.shade800),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        '정확한 정식일로 확인해주세요 (탭하면 수정 화면으로 이동)',
                        style: TextStyle(fontSize: 11, color: Colors.orange.shade800, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _tag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: TextStyle(fontSize: 10.5, color: color, fontWeight: FontWeight.w700)),
    );
  }
}
