import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

import 'providers/farm_provider.dart';
import 'screens/home_shell.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ko_KR');
  runApp(const GinsengFarmApp());
}

class GinsengFarmApp extends StatelessWidget {
  const GinsengFarmApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => FarmProvider()..load()),
      ],
      child: MaterialApp(
        title: '인삼 AI 영농일지',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        home: const HomeShell(),
      ),
    );
  }
}
