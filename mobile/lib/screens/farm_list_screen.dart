import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/farm.dart';
import '../providers/farm_provider.dart';
import '../widgets/common.dart';
import 'farm_form_screen.dart';

class FarmListScreen extends StatelessWidget {
  const FarmListScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<FarmProvider>();

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
        onRefresh: () => provider.load(),
        child: provider.isLoading && provider.farms.isEmpty
            ? const LoadingView()
            : provider.error != null && provider.farms.isEmpty
                ? ErrorView(message: '농장 목록을 불러오지 못했습니다.\n${provider.error}', onRetry: provider.load)
                : provider.farms.isEmpty
                    ? const EmptyView(message: '등록된 농장이 없습니다.\n우측 하단 버튼으로 농장을 등록해보세요.', icon: Icons.grass_outlined)
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 90),
                        itemCount: provider.farms.length,
                        itemBuilder: (context, i) => _FarmCard(farm: provider.farms[i]),
                      ),
      ),
    );
  }
}

class _FarmCard extends StatelessWidget {
  final Farm farm;
  const _FarmCard({required this.farm});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () async {
          final updated = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => FarmFormScreen(farm: farm)),
          );
          if (updated == true && context.mounted) {
            context.read<FarmProvider>().load();
          }
        },
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
                  const SizedBox(width: 6),
                  _tag('${farm.cultivationYear}년근', Colors.orange),
                ],
              ),
              const SizedBox(height: 6),
              Text(farm.address, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600)),
              const SizedBox(height: 4),
              Text('면적 ${farm.areaPyeong.toStringAsFixed(0)}평 (${farm.areaM2.toStringAsFixed(0)}㎡)',
                  style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600)),
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
