import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/auth.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../services/app_config.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _ctrl = TextEditingController();
  final _api = ApiService();
  bool _loading = true;
  MeResponse? _me;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final url = await AppConfig.getBaseUrl();
    _ctrl.text = url;
    try {
      _me = await _api.me();
    } catch (_) {
      // 무시: 계정 정보는 참고용이라 실패해도 서버 주소 설정은 그대로 사용 가능해야 함
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _saveServerUrl() async {
    await AppConfig.setBaseUrl(_ctrl.text);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('저장되었습니다. 앱을 재시작하면 완전히 적용됩니다.')));
    }
  }

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('로그아웃'),
        content: const Text('로그아웃 하시겠습니까?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('취소')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('로그아웃')),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await context.read<AuthProvider>().logout();
      // SettingsScreen은 Navigator.push로 쌓인 화면이라, AuthGate가 다시 빌드되어
      // LoginScreen을 반환해도 그 위에 남아있으면 화면이 안 바뀐 것처럼 보인다.
      // 루트(AuthGate)까지 스택을 비워야 로그인 화면이 실제로 보인다.
      if (mounted) Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_me != null) ...[
                  const Text('계정 정보', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 10),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_me!.household.name, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Text('농가 코드', style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppColors.greenLight,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  _me!.household.joinCode,
                                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5, letterSpacing: 1),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '가족·공동경영자에게 이 코드를 알려주면 같은 농가로 함께 관리할 수 있습니다.',
                            style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
                          ),
                          const Divider(height: 20),
                          Text('함께 관리 중인 사람 (${_me!.members.length}명)',
                              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5)),
                          const SizedBox(height: 6),
                          ..._me!.members.map(
                            (m) => Padding(
                              padding: const EdgeInsets.symmetric(vertical: 3),
                              child: Row(
                                children: [
                                  const Icon(Icons.person, size: 14, color: AppColors.green),
                                  const SizedBox(width: 6),
                                  Text('${m.name} (${m.phone})', style: const TextStyle(fontSize: 12.5)),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
                const Text('API 서버 주소', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(
                  '안드로이드 에뮬레이터는 10.0.2.2, iOS 시뮬레이터/실기기는 PC의 IP 주소를 사용하세요.',
                  style: TextStyle(fontSize: 11.5, color: Colors.grey.shade600),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _ctrl,
                  decoration: const InputDecoration(hintText: 'http://10.0.2.2:8000'),
                  keyboardType: TextInputType.url,
                ),
                const SizedBox(height: 12),
                ElevatedButton(onPressed: _saveServerUrl, child: const Text('서버 주소 저장')),
                const SizedBox(height: 28),
                OutlinedButton.icon(
                  onPressed: _confirmLogout,
                  icon: const Icon(Icons.logout, color: AppColors.red),
                  label: const Text('로그아웃', style: TextStyle(color: AppColors.red)),
                  style: OutlinedButton.styleFrom(side: const BorderSide(color: AppColors.red)),
                ),
              ],
            ),
    );
  }
}
