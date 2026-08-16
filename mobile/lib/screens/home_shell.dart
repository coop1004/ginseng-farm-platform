import 'package:flutter/material.dart';

import 'dashboard_screen.dart';
import 'diagnosis_screen.dart';
import 'farm_list_screen.dart';
import 'stats_screen.dart';
import 'work_log_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  final _screens = const [
    DashboardScreen(),
    FarmListScreen(),
    WorkLogScreen(),
    DiagnosisScreen(),
    StatsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home_outlined), activeIcon: Icon(Icons.home), label: '홈'),
          BottomNavigationBarItem(icon: Icon(Icons.grass_outlined), activeIcon: Icon(Icons.grass), label: '농장'),
          BottomNavigationBarItem(
              icon: Icon(Icons.edit_note_outlined), activeIcon: Icon(Icons.edit_note), label: '영농일지'),
          BottomNavigationBarItem(
              icon: Icon(Icons.biotech_outlined), activeIcon: Icon(Icons.biotech), label: '병해충일지'),
          BottomNavigationBarItem(
              icon: Icon(Icons.bar_chart_outlined), activeIcon: Icon(Icons.bar_chart), label: '통계'),
        ],
      ),
    );
  }
}
