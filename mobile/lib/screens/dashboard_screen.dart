import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/app_notification.dart';
import '../models/crop.dart';
import '../models/stats.dart';
import '../providers/auth_provider.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'community_screen.dart';
import 'diagnosis_form_screen.dart';
import 'farm_form_screen.dart';
import 'pest_reference_screen.dart';
import 'settings_screen.dart';
import 'stats_screen.dart';
import 'work_log_form_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _api = ApiService();
  StatsSummary? _summary;
  List<AppNotification> _notifications = [];
  bool _loading = true;
  int? _lastLoadedCropId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final cropId = mounted ? context.read<CropProvider>().activeCrop?.id : null;
      final results = await Future.wait([
        _api.getStatsSummary(cropId: cropId),
        _api.getNotifications(),
      ]);
      setState(() {
        _summary = results[0] as StatsSummary;
        _notifications = (results[1] as List<AppNotification>).take(5).toList();
      });
    } catch (_) {
      // 홈 화면은 오프라인이어도 조용히 실패 (개별 탭에서 재시도 가능)
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final farmProvider = context.watch<FarmProvider>();
    final auth = context.watch<AuthProvider>();
    final cropProvider = context.watch<CropProvider>();
    final today = DateFormat('yyyy년 MM월 dd일 (E)', 'ko_KR').format(DateTime.now());

    // CropProvider는 로그인 직후 비동기로 채워지고(작물 전환 시에도 바뀜) 활성 작물이
    // 달라지면 그 작물 기준으로 요약을 다시 불러온다. 등록 작물이 1개뿐인 농가는 activeCrop이
    // 한 번 정해진 뒤로는 안 바뀌므로 최초 1회만 다시 로드되고 이후엔 지금과 동일하게 동작한다.
    final activeCropId = cropProvider.activeCrop?.id;
    if (activeCropId != _lastLoadedCropId) {
      _lastLoadedCropId = activeCropId;
      WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('함께 쓰는 AI영농일지'),
        actions: [
          if (cropProvider.hasMultipleCrops) _CropSwitcher(cropProvider: cropProvider),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await Future.wait([_load(), farmProvider.load()]);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            Text(today, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600)),
            const SizedBox(height: 4),
            Text(
              '${auth.user?.name ?? ''}대표님, 오늘도 건강한 농사되세요 🌱',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            if (auth.household != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  '${auth.household!.name} · 농가 코드 ${auth.household!.joinCode}',
                  style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500),
                ),
              ),
            const SizedBox(height: 18),
            _quickActions(context),
            const SectionTitle('한눈에 보는 현황'),
            _loading
                ? const SizedBox(height: 80, child: LoadingView())
                : _summary == null
                    ? Text('서버에 연결할 수 없습니다. 우측 상단 설정에서 서버 주소를 확인해주세요.',
                        style: TextStyle(color: Colors.grey.shade500, fontSize: 12.5))
                    : _summaryRow(_summary!),
            const SectionTitle('농자재사 처방 알림', subtitle: '관리자가 보낸 최신 알림'),
            if (_notifications.isEmpty)
              Text('수신된 알림이 없습니다.', style: TextStyle(color: Colors.grey.shade500, fontSize: 12.5))
            else
              ..._notifications.map((n) => _NotificationTile(notification: n)),
          ],
        ),
      ),
    );
  }

  Widget _quickActions(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _actionButton(
                context,
                icon: Icons.add_business_outlined,
                label: '농장 등록',
                color: AppColors.green,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const FarmFormScreen())),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _actionButton(
                context,
                icon: Icons.edit_note_outlined,
                label: '작업 기록',
                color: AppColors.blue,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const WorkLogFormScreen())),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _actionButton(
                context,
                icon: Icons.biotech_outlined,
                label: 'AI 진단',
                color: AppColors.orange,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DiagnosisFormScreen())),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _actionButton(
                context,
                icon: Icons.menu_book_outlined,
                label: '병해충 정보',
                color: Colors.purple,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PestReferenceScreen())),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _CommunityEntryCard(
          onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CommunityScreen())),
        ),
      ],
    );
  }

  Widget _actionButton(BuildContext context,
      {required IconData icon, required String label, required Color color, required VoidCallback onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            children: [
              Icon(icon, color: color, size: 26),
              const SizedBox(height: 8),
              Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _summaryRow(StatsSummary s) {
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const StatsScreen())),
      child: Row(
        children: [
          Expanded(child: _miniStat('농장', '${s.totalFarms}')),
          Expanded(child: _miniStat('영농일지', '${s.totalWorkLogs}')),
          Expanded(child: _miniStat('AI진단', '${s.totalDiagnoses}')),
          Expanded(
              child: _miniStat(
                  '정확도', s.aiVsActual['accuracy_percent'] != null ? '${s.aiVsActual['accuracy_percent']}%' : '-')),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 3),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 2),
            Text(label, style: TextStyle(fontSize: 10.5, color: Colors.grey.shade600)),
          ],
        ),
      ),
    );
  }
}

class _CommunityEntryCard extends StatelessWidget {
  final VoidCallback onTap;
  const _CommunityEntryCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          child: Row(
            children: [
              const Icon(Icons.groups_outlined, color: AppColors.blue, size: 24),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('커뮤니티', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
                    Text('컨설턴트 공지·팁, 농가끼리 정보 공유',
                        style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: Colors.grey.shade400),
            ],
          ),
        ),
      ),
    );
  }
}

class _CropSwitcher extends StatelessWidget {
  final CropProvider cropProvider;
  const _CropSwitcher({required this.cropProvider});

  @override
  Widget build(BuildContext context) {
    final active = cropProvider.activeCrop;
    return PopupMenuButton<Crop>(
      tooltip: '작물 전환',
      initialValue: active,
      onSelected: (crop) => cropProvider.setActiveCrop(crop),
      itemBuilder: (context) => cropProvider.myCrops
          .map((c) => PopupMenuItem(value: c, child: Text('${c.iconEmoji ?? ''} ${c.nameKr}'.trim())))
          .toList(),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('${active?.iconEmoji ?? ''} ${active?.nameKr ?? ''}'.trim(),
                style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Colors.white)),
            const Icon(Icons.expand_more, color: Colors.white, size: 18),
          ],
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final AppNotification notification;
  const _NotificationTile({required this.notification});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: const CircleAvatar(
          backgroundColor: AppColors.greenLight,
          child: Icon(Icons.mark_email_unread_outlined, color: AppColors.green, size: 18),
        ),
        title: Text(notification.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
        subtitle: Text(
          '${notification.farmName ?? ''} · ${notification.recommendedProduct ?? ''}',
          style: TextStyle(fontSize: 11.5, color: Colors.grey.shade600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Text(DateFormat('MM.dd').format(notification.createdAt), style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
        onTap: () => showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: Text(notification.title),
            content: Text(notification.message),
            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('확인'))],
          ),
        ),
      ),
    );
  }
}
