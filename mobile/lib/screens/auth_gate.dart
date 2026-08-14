import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import 'home_shell.dart';
import 'login_screen.dart';

/// 로그인 상태에 따라 로그인 화면 또는 메인 화면을 보여준다.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    context.read<AuthProvider>().tryAutoLogin();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    switch (auth.status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.unauthenticated:
        return const LoginScreen();
      case AuthStatus.authenticated:
        // 로그인 직후/자동로그인 성공 시 농장 목록과 등록 작물(활성 작물 포함)을 새로 불러온다.
        WidgetsBinding.instance.addPostFrameCallback((_) {
          context.read<FarmProvider>().load();
          context.read<CropProvider>().loadFromHousehold(auth.household);
        });
        return const HomeShell();
    }
  }
}
