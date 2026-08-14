import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _householdNameCtrl = TextEditingController();
  final _joinCodeCtrl = TextEditingController();

  bool _isNewHousehold = true;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    _passwordCtrl.dispose();
    _householdNameCtrl.dispose();
    _joinCodeCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final auth = context.read<AuthProvider>();

    final ok = _isNewHousehold
        ? await auth.registerNewHousehold(
            phone: _phoneCtrl.text.trim(),
            password: _passwordCtrl.text,
            name: _nameCtrl.text.trim(),
            householdName: _householdNameCtrl.text.trim(),
          )
        : await auth.registerJoinHousehold(
            phone: _phoneCtrl.text.trim(),
            password: _passwordCtrl.text,
            name: _nameCtrl.text.trim(),
            joinCode: _joinCodeCtrl.text.trim(),
          );

    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(auth.error ?? '가입에 실패했습니다.')));
    } else if (ok && mounted) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 40),
          children: [
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: true, label: Text('새 농가 등록'), icon: Icon(Icons.add_home_outlined)),
                ButtonSegment(value: false, label: Text('기존 농가 합류'), icon: Icon(Icons.group_add_outlined)),
              ],
              selected: {_isNewHousehold},
              onSelectionChanged: (s) => setState(() => _isNewHousehold = s.first),
            ),
            const SizedBox(height: 6),
            Text(
              _isNewHousehold
                  ? '새로운 농가를 등록합니다. 가입 후 발급되는 농가 코드를 가족·공동경영자에게 알려주면 같은 농가로 함께 관리할 수 있습니다.'
                  : '이미 등록된 농가의 코드를 입력하면, 그 농가의 필지와 기록을 함께 보고 관리할 수 있습니다.',
              style: TextStyle(fontSize: 11.5, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 20),
            TextFormField(
              controller: _nameCtrl,
              decoration: const InputDecoration(labelText: '이름 *', prefixIcon: Icon(Icons.person_outline)),
              validator: (v) => (v == null || v.trim().isEmpty) ? '이름을 입력해주세요.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: '전화번호 *', prefixIcon: Icon(Icons.phone_outlined)),
              validator: (v) => (v == null || v.trim().isEmpty) ? '전화번호를 입력해주세요.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _passwordCtrl,
              obscureText: true,
              decoration: const InputDecoration(labelText: '비밀번호 *', prefixIcon: Icon(Icons.lock_outline)),
              validator: (v) => (v == null || v.length < 4) ? '비밀번호는 4자 이상 입력해주세요.' : null,
            ),
            const SizedBox(height: 12),
            if (_isNewHousehold)
              TextFormField(
                controller: _householdNameCtrl,
                decoration: const InputDecoration(labelText: '농가명 *', hintText: '예: 김인삼 농가', prefixIcon: Icon(Icons.home_outlined)),
                validator: (v) => (v == null || v.trim().isEmpty) ? '농가명을 입력해주세요.' : null,
              )
            else
              TextFormField(
                controller: _joinCodeCtrl,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(labelText: '농가 코드 *', hintText: '예: DEMO01', prefixIcon: Icon(Icons.key_outlined)),
                validator: (v) => (v == null || v.trim().isEmpty) ? '농가 코드를 입력해주세요.' : null,
              ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: auth.isLoading ? null : _submit,
              child: auth.isLoading
                  ? const SizedBox(
                      height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : Text(_isNewHousehold ? '농가 등록하고 시작하기' : '농가 합류하기'),
            ),
          ],
        ),
      ),
    );
  }
}
