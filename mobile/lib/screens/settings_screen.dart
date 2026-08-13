import 'package:flutter/material.dart';

import '../services/app_config.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _ctrl = TextEditingController();
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    AppConfig.getBaseUrl().then((url) {
      _ctrl.text = url;
      setState(() => _loading = false);
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await AppConfig.setBaseUrl(_ctrl.text);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('저장되었습니다. 앱을 재시작하면 완전히 적용됩니다.')));
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('서버 설정')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
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
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: _save, child: const Text('저장')),
                ],
              ),
            ),
    );
  }
}
