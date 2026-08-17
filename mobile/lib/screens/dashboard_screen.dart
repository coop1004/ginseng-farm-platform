import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/app_notification.dart';
import '../models/crop.dart';
import '../providers/auth_provider.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'community_screen.dart';
import 'diagnosis_form_screen.dart';
import 'pest_reference_screen.dart';
import 'settings_screen.dart';
import 'work_log_form_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _api = ApiService();
  List<AppNotification> _notifications = [];
  String? _riskLevel;
  int? _lastLoadedCropId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final notifications = await _api.getNotifications();
      setState(() => _notifications = notifications.take(5).toList());
    } catch (_) {
      // 홈 화면은 오프라인이어도 조용히 실패 (개별 탭에서 재시도 가능)
    }
    await _loadRiskSignal();
  }

  Future<void> _loadRiskSignal() async {
    if (!mounted) return;
    final activeCropId = context.read<CropProvider>().activeCrop?.id;
    final farms = context.read<FarmProvider>().forCrop(activeCropId);
    if (farms.isEmpty) {
      if (mounted) setState(() => _riskLevel = null);
      return;
    }
    try {
      final level = await _api.getRegionalRiskSignal(farms.first.id);
      if (mounted) setState(() => _riskLevel = level);
    } catch (_) {
      // 신호등은 부가 정보라 실패해도 조용히 무시 (홈 화면 다른 기능에 영향 없음)
    }
  }

  @override
  Widget build(BuildContext context) {
    final farmProvider = context.watch<FarmProvider>();
    final auth = context.watch<AuthProvider>();
    final cropProvider = context.watch<CropProvider>();
    final today = DateFormat('yyyy년 MM월 dd일 (E)', 'ko_KR').format(DateTime.now());

    // CropProvider는 로그인 직후 비동기로 채워진다(작물 전환 시에도 바뀜) - 최초 1회
    // activeCrop이 정해질 때 알림을 한 번 더 불러와 로그인 직후의 빈 상태를 채운다.
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
            const SizedBox(height: 6),
            // 이름 길이와 무관하게 항상 이름 뒤(쉼표)에서 줄이 바뀌도록 두 줄을 별도 Text로 분리한다
            // (자동 줄바꿈에 맡기면 "건강한 농/사되세요"처럼 단어 중간이 잘리는 문제가 있었음).
            Text(
              '${auth.user?.name ?? ''}대표님,',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
            ),
            const Text(
              '오늘도 든든한 하루되세요 🌱',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 18),
            _quickActions(context),
            const SectionTitle('회사 공지·처방알림', subtitle: '관리자가 보낸 최신 알림'),
            if (_notifications.isEmpty)
              Text('수신된 알림이 없습니다.', style: TextStyle(color: Colors.grey.shade500, fontSize: 12.5))
            else
              ..._notifications.map((n) => _NotificationTile(notification: n)),
            if (_riskLevel != null) ...[
              const SizedBox(height: 4),
              _RegionalRiskBadge(level: _riskLevel!),
            ],
            const SectionTitle('병해충 정보', subtitle: '카테고리별로 참고자료를 확인하세요'),
            const _PestCategoryRow(),
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
              child: _primaryActionButton(
                context,
                icon: Icons.edit_note_outlined,
                label: '작업 기록',
                color: AppColors.blue,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const WorkLogFormScreen())),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _primaryActionButton(
                context,
                icon: Icons.biotech_outlined,
                label: '병해충 진단',
                color: AppColors.orange,
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DiagnosisFormScreen())),
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

  Widget _primaryActionButton(BuildContext context,
      {required IconData icon, required String label, required Color color, required VoidCallback onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Column(
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 10),
              Text(label, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
            ],
          ),
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
                    const Text('컨설턴트 공지', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
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

/// 지역 위험 신호등 배지 - "주의"/"경계" 등급만 표시하고, 병해충명·건수 같은 구체 정보는
/// 절대 노출하지 않는다(이웃 농가 식별 방지, 서버 응답 자체에도 등급 외 정보가 없음).
class _RegionalRiskBadge extends StatelessWidget {
  final String level;
  const _RegionalRiskBadge({required this.level});

  Color get _color => level == '경계' ? AppColors.red : AppColors.orange;

  // 병해충명·정확한 건수는 절대 노출하지 않되, 등급을 가르는 기준(일반 정책) 자체는
  // 특정 농가를 특정하지 않는 정보라 안내해도 안전하다 - 사용자가 "왜 이 등급인지"
  // 판단할 수 있도록 최소한의 근거를 제공한다.
  String get _criteriaText => level == '경계'
      ? '최근 7일간 같은 병해충이 우리 지역에서 6건 이상 확인되면 "경계" 단계로 안내돼요.'
      : '최근 7일간 같은 병해충이 우리 지역에서 3건 이상 확인되면 "주의" 단계로 안내돼요.';

  void _showInfo(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('우리 지역 병해충 신호: $level'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('이번 주 우리 지역에서 병해충 신고가 평소보다 늘었어요. 예방 관리를 확인해보세요.'),
            const SizedBox(height: 10),
            Text(_criteriaText, style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('닫기')),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PestReferenceScreen()));
            },
            child: const Text('예방 관리 확인'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => _showInfo(context),
      borderRadius: BorderRadius.circular(14),
      child: Card(
        color: _color.withOpacity(0.08),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: _color, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Text('우리 지역 병해충 신호: $level',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _color)),
              ),
              Icon(Icons.chevron_right, color: Colors.grey.shade400),
            ],
          ),
        ),
      ),
    );
  }
}

/// 홈 화면 하단의 병해충 정보 진입점 — 병해/해충/생리장애 3개 카테고리 아이콘.
/// PestReference.type이 이미 이 3가지 값으로 채워져 있어(diagnosisTypes와 동일)
/// 별도 분류 기준 없이 그대로 필터 조건으로 재사용한다.
class _PestCategoryRow extends StatelessWidget {
  const _PestCategoryRow();

  static const _categories = [
    (type: '병해', icon: Icons.coronavirus_outlined),
    (type: '해충', icon: Icons.bug_report_outlined),
    (type: '생리장애', icon: Icons.eco_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      children: _categories
          .map(
            (c) => Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => PestReferenceScreen(initialType: c.type)),
                  ),
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Column(
                        children: [
                          Icon(c.icon, color: diagnosisTypeColors[c.type] ?? Colors.grey, size: 24),
                          const SizedBox(height: 8),
                          Text(c.type, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          )
          .toList(),
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
