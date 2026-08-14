import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/crop.dart';
import '../models/diagnosis.dart';
import '../models/pest_reference.dart';
import '../providers/crop_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

/// 작물을 선택하면 그 작물의 병해충 목록·방제 정보가 달라지는 것을 보여주는 화면.
/// 인삼은 실서비스 데이터, 고추/배추는 구조 확장을 보여주기 위한 샘플 데이터다.
class PestReferenceScreen extends StatefulWidget {
  const PestReferenceScreen({super.key});

  @override
  State<PestReferenceScreen> createState() => _PestReferenceScreenState();
}

class _PestReferenceScreenState extends State<PestReferenceScreen> {
  final _api = ApiService();

  List<Crop> _crops = [];
  Crop? _selectedCrop;
  List<PestReference> _references = [];
  bool _loadingCrops = true;
  bool _loadingRefs = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCrops();
  }

  Future<void> _loadCrops() async {
    setState(() {
      _loadingCrops = true;
      _error = null;
    });
    try {
      // 이 농가가 등록한 작물만 칩으로 보여준다 — 인삼만 등록한 농가는 칩 자체가 하나뿐이라
      // 사실상 선택 UI가 없는 것과 동일하게 보인다.
      final cropProvider = context.read<CropProvider>();
      final crops = cropProvider.myCrops;
      setState(() {
        _crops = crops;
        _selectedCrop = cropProvider.activeCrop ?? (crops.isNotEmpty ? crops.first : null);
      });
      if (_selectedCrop != null) await _loadReferences(_selectedCrop!.id);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loadingCrops = false);
    }
  }

  Future<void> _loadReferences(int cropId) async {
    setState(() => _loadingRefs = true);
    try {
      final refs = await _api.getPestReferences(cropId: cropId);
      setState(() => _references = refs);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loadingRefs = false);
    }
  }

  void _onCropSelected(Crop crop) {
    setState(() => _selectedCrop = crop);
    _loadReferences(crop.id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('병해충 참고자료')),
      body: _loadingCrops
          ? const LoadingView()
          : _error != null && _crops.isEmpty
              ? ErrorView(message: '불러오지 못했습니다.\n$_error', onRetry: _loadCrops)
              : Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                      child: Wrap(
                        spacing: 8,
                        children: _crops
                            .map((c) => ChoiceChip(
                                  label: Text('${c.iconEmoji ?? ''} ${c.nameKr}'.trim()),
                                  selected: _selectedCrop?.id == c.id,
                                  onSelected: (_) => _onCropSelected(c),
                                ))
                            .toList(),
                      ),
                    ),
                    if (_selectedCrop?.isSampleData == true)
                      Container(
                        margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.orange.shade50,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Colors.orange.shade200),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.science_outlined, size: 16, color: Colors.orange.shade800),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                '샘플 데이터 · 베타/프로토타입 — 실제 학습된 진단 모델이 아직 없어 구조 시연용으로 등록된 참고자료입니다.',
                                style: TextStyle(fontSize: 11.5, color: Colors.orange.shade900),
                              ),
                            ),
                          ],
                        ),
                      ),
                    Expanded(
                      child: _loadingRefs
                          ? const LoadingView()
                          : _references.isEmpty
                              ? const EmptyView(message: '등록된 참고자료가 없습니다.')
                              : ListView.builder(
                                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
                                  itemCount: _references.length,
                                  itemBuilder: (context, i) => _PestReferenceCard(reference: _references[i], api: _api),
                                ),
                    ),
                  ],
                ),
    );
  }
}

class _PestReferenceCard extends StatelessWidget {
  final PestReference reference;
  final ApiService api;
  const _PestReferenceCard({required this.reference, required this.api});

  @override
  Widget build(BuildContext context) {
    final typeColor = diagnosisTypeColors[reference.type] ?? Colors.grey;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (reference.photoPath != null)
              FutureBuilder<String>(
                future: api.photoUrlAsync(reference.photoPath),
                builder: (context, snap) {
                  if (!snap.hasData || snap.data!.isEmpty) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.network(snap.data!, height: 140, width: double.infinity, fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => const SizedBox.shrink()),
                    ),
                  );
                },
              ),
            Row(
              children: [
                _chip(reference.type, typeColor),
                if (reference.isSampleData) ...[
                  const SizedBox(width: 6),
                  _chip('샘플 데이터', Colors.orange),
                ],
                const Spacer(),
              ],
            ),
            const SizedBox(height: 8),
            Text(reference.nameKr, style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800)),
            if (reference.nameEn != null)
              Text(reference.nameEn!, style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
            if (reference.symptoms != null) ...[
              const SizedBox(height: 8),
              Text(reference.symptoms!, style: const TextStyle(fontSize: 12.5, height: 1.5)),
            ],
            if (reference.ecoTreatments.isNotEmpty) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  const Icon(Icons.eco, size: 14, color: AppColors.green),
                  const SizedBox(width: 4),
                  Text('친환경 방제', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Colors.grey.shade700)),
                ],
              ),
              ...reference.ecoTreatments.map((t) => _treatmentLine(t)),
            ],
            if (reference.chemicalTreatments.isNotEmpty) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.science_outlined, size: 14, color: Colors.grey.shade600),
                  const SizedBox(width: 4),
                  Text('화학적 관리법', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Colors.grey.shade700)),
                ],
              ),
              ...reference.chemicalTreatments.map((t) => _treatmentLine(t)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _treatmentLine(TreatmentItem t) {
    return Padding(
      padding: const EdgeInsets.only(top: 4, left: 18),
      child: Text('· ${t.productName} — ${t.usage}', style: const TextStyle(fontSize: 12, height: 1.4)),
    );
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: TextStyle(fontSize: 10.5, color: color, fontWeight: FontWeight.w700)),
    );
  }
}
