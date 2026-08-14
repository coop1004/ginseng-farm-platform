import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/diagnosis.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class DiagnosisResultScreen extends StatefulWidget {
  final Diagnosis diagnosis;
  final bool isNew;

  const DiagnosisResultScreen({super.key, required this.diagnosis, this.isNew = false});

  @override
  State<DiagnosisResultScreen> createState() => _DiagnosisResultScreenState();
}

class _DiagnosisResultScreenState extends State<DiagnosisResultScreen> {
  late Diagnosis diagnosis;
  bool _submittingFeedback = false;
  bool _submittingFinal = false;

  @override
  void initState() {
    super.initState();
    diagnosis = widget.diagnosis;
  }

  Future<void> _openFinalDiagnosisDialog() async {
    final nameCtrl = TextEditingController(text: diagnosis.finalDiseaseName ?? '');
    final noteCtrl = TextEditingController(text: diagnosis.finalDiagnosisNote ?? '');
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('진단명 직접 입력'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('현장을 직접 확인하신 결과를 입력해주세요. AI 판단보다 우선 반영됩니다.',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            const SizedBox(height: 14),
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(labelText: '진단명(병해충명) *'),
              autofocus: true,
            ),
            const SizedBox(height: 10),
            TextField(
              controller: noteCtrl,
              decoration: const InputDecoration(labelText: '메모(선택)'),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('취소')),
          FilledButton(
            onPressed: () {
              if (nameCtrl.text.trim().isEmpty) return;
              Navigator.pop(context, true);
            },
            child: const Text('저장'),
          ),
        ],
      ),
    );
    if (result != true) return;

    setState(() => _submittingFinal = true);
    try {
      final updated = await ApiService().submitFinalDiagnosis(
        diagnosisId: diagnosis.id,
        diseaseName: nameCtrl.text.trim(),
        note: noteCtrl.text.trim().isEmpty ? null : noteCtrl.text.trim(),
      );
      setState(() => diagnosis = updated);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('진단명이 저장되었습니다.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('저장 실패: $e')));
      }
    } finally {
      if (mounted) setState(() => _submittingFinal = false);
    }
  }

  Future<void> _submitFeedback(bool correct) async {
    setState(() => _submittingFeedback = true);
    try {
      final updated = await ApiService().submitDiagnosisFeedback(
        diagnosisId: diagnosis.id,
        correct: correct,
      );
      setState(() => diagnosis = updated);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('피드백이 저장되었습니다. 감사합니다.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('피드백 저장 실패: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _submittingFeedback = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isNew = widget.isNew;
    final typeColor = diagnosisTypeColors[diagnosis.diagnosisType] ?? Colors.grey;
    final api = ApiService();

    return Scaffold(
      appBar: AppBar(title: Text(isNew ? 'AI 진단 결과' : '진단 상세')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
        children: [
          if (isNew)
            Container(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.greenLight, borderRadius: BorderRadius.circular(10)),
              child: const Row(
                children: [
                  Icon(Icons.check_circle, color: AppColors.green, size: 18),
                  SizedBox(width: 8),
                  Expanded(child: Text('AI 분석이 완료되었습니다. 아래 처방 내용을 확인해주세요.', style: TextStyle(fontSize: 12.5))),
                ],
              ),
            ),
          if (diagnosis.photoPaths.isNotEmpty || diagnosis.photoPath != null)
            _PhotoCarousel(
              photoPaths: diagnosis.photoPaths.isNotEmpty ? diagnosis.photoPaths : [diagnosis.photoPath!],
              api: api,
            ),
          const SizedBox(height: 14),
          Row(
            children: [
              _chip(diagnosis.diagnosisType, typeColor),
              const SizedBox(width: 6),
              _chip(diagnosis.cropName, Colors.grey.shade600),
              const Spacer(),
              Text(DateFormat('yyyy.MM.dd').format(diagnosis.occurrenceDate),
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(diagnosis.effectiveDiseaseName ?? '진단 결과 없음',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
              ),
              if (diagnosis.finalDiseaseName != null)
                _chip(diagnosis.finalDiagnosisSource == 'expert' ? '전문가 확정' : '농가 직접확인', AppColors.blue),
            ],
          ),
          if (diagnosis.finalDiseaseName != null && diagnosis.aiDiseaseName != null && diagnosis.aiDiseaseName != diagnosis.finalDiseaseName)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text('AI 판단: ${diagnosis.aiDiseaseName}', style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
            ),
          if (diagnosis.finalDiseaseName == null && diagnosis.aiDiseaseNameEn != null)
            Text(diagnosis.aiDiseaseNameEn!, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade500)),
          const SizedBox(height: 6),
          if (diagnosis.aiConfidence != null)
            Row(
              children: [
                Icon(Icons.insights, size: 15, color: Colors.grey.shade600),
                const SizedBox(width: 4),
                Text('AI 확신도 ${(diagnosis.aiConfidence! * 100).toStringAsFixed(0)}%',
                    style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600, fontWeight: FontWeight.w600)),
              ],
            ),
          const SizedBox(height: 14),
          _buildFinalDiagnosisCard(),
          const SizedBox(height: 14),
          if (diagnosis.aiSymptoms != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('특징 및 증상', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                    const SizedBox(height: 6),
                    Text(diagnosis.aiSymptoms!, style: const TextStyle(fontSize: 13, height: 1.5)),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 14),
          _WeatherRow(diagnosis: diagnosis),
          const SizedBox(height: 20),
          const _SectionHeader(icon: Icons.eco, title: '친환경/유기농 방제 자재 (최우선 추천)', color: AppColors.green),
          const SizedBox(height: 8),
          if (diagnosis.ecoTreatments.isEmpty)
            Text('추천 자재가 없습니다.', style: TextStyle(color: Colors.grey.shade500))
          else
            ...diagnosis.ecoTreatments.map((t) => _TreatmentCard(item: t, highlight: true)),
          const SizedBox(height: 18),
          const _SectionHeader(icon: Icons.science_outlined, title: '화학적 관리법 (보조 정보)', color: Colors.grey),
          const SizedBox(height: 8),
          if (diagnosis.chemicalTreatments.isEmpty)
            Text('해당 없음', style: TextStyle(color: Colors.grey.shade500))
          else
            ...diagnosis.chemicalTreatments.map((t) => _TreatmentCard(item: t, highlight: false)),
          const SizedBox(height: 20),
          _buildFeedbackCard(),
        ],
      ),
    );
  }

  Widget _buildFinalDiagnosisCard() {
    if (diagnosis.finalDiseaseName != null) {
      return Card(
        color: const Color(0xFFEAF1FB),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.fact_check_outlined, size: 17, color: AppColors.blue),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      diagnosis.finalDiagnosisSource == 'expert' ? '전문가가 확정한 진단' : '직접 확인한 진단',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                    ),
                  ),
                  TextButton(
                    onPressed: _submittingFinal ? null : _openFinalDiagnosisDialog,
                    child: const Text('수정', style: TextStyle(fontSize: 12)),
                  ),
                ],
              ),
              if (diagnosis.finalDiagnosisNote != null && diagnosis.finalDiagnosisNote!.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(diagnosis.finalDiagnosisNote!, style: const TextStyle(fontSize: 12.5, height: 1.4)),
              ],
              if (diagnosis.finalDiagnosisBy != null) ...[
                const SizedBox(height: 4),
                Text('입력: ${diagnosis.finalDiagnosisBy}', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
              ],
            ],
          ),
        ),
      );
    }
    return OutlinedButton.icon(
      onPressed: _submittingFinal ? null : _openFinalDiagnosisDialog,
      icon: const Icon(Icons.edit_note, size: 17),
      label: const Text('AI 진단이 실제와 다른가요? 직접 입력하기'),
    );
  }

  Widget _buildFeedbackCard() {
    final confirmed = diagnosis.farmerConfirmedCorrect;
    if (confirmed != null) {
      return Card(
        color: const Color(0xFFF3F6F3),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Icon(confirmed ? Icons.check_circle : Icons.info_outline,
                  size: 18, color: confirmed ? AppColors.green : Colors.grey.shade600),
              const SizedBox(width: 8),
              Text(
                confirmed ? '실제와 일치한다고 확인해주셨습니다.' : '실제와 달랐다고 확인해주셨습니다.',
                style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ),
      );
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('AI 진단이 실제와 맞았나요?',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
            const SizedBox(height: 4),
            Text('농가님의 확인은 AI 진단 정확도 통계에 반영됩니다.',
                style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _submittingFeedback ? null : () => _submitFeedback(true),
                    icon: const Icon(Icons.thumb_up_outlined, size: 16),
                    label: const Text('맞았어요'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _submittingFeedback ? null : () => _submitFeedback(false),
                    icon: const Icon(Icons.thumb_down_outlined, size: 16),
                    label: const Text('아니었어요'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w700)),
    );
  }
}

class _WeatherRow extends StatelessWidget {
  final Diagnosis diagnosis;
  const _WeatherRow({required this.diagnosis});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFFF3F6F3),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _weatherItem(Icons.thermostat, '${diagnosis.weatherTempC?.toStringAsFixed(1) ?? '-'}℃', '기온'),
            _weatherItem(Icons.water_drop_outlined, '${diagnosis.weatherHumidityPercent?.toStringAsFixed(0) ?? '-'}%', '습도'),
            _weatherItem(Icons.grain, '${diagnosis.weatherRainfallMm?.toStringAsFixed(1) ?? '-'}mm', '강우량'),
            _weatherItem(Icons.air, '${diagnosis.weatherWindMs?.toStringAsFixed(1) ?? '-'}m/s', '풍속'),
          ],
        ),
      ),
    );
  }

  Widget _weatherItem(IconData icon, String value, String label) {
    return Column(
      children: [
        Icon(icon, size: 18, color: Colors.grey.shade700),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5)),
        Text(label, style: TextStyle(fontSize: 10.5, color: Colors.grey.shade500)),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final Color color;
  const _SectionHeader({required this.icon, required this.title, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 6),
        Text(title, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: color)),
      ],
    );
  }
}

class _TreatmentCard extends StatelessWidget {
  final TreatmentItem item;
  final bool highlight;
  const _TreatmentCard({required this.item, required this.highlight});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: highlight ? AppColors.greenLight : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: highlight ? AppColors.green.withOpacity(0.3) : Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (highlight) const Icon(Icons.eco, size: 15, color: AppColors.green),
                if (highlight) const SizedBox(width: 4),
                Expanded(
                  child: Text(item.productName, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text('성분: ${item.activeIngredient}', style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
            const SizedBox(height: 4),
            Text('사용법: ${item.usage}', style: const TextStyle(fontSize: 12.5, height: 1.4)),
            if (item.note != null && item.note!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('※ ${item.note}', style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
            ],
          ],
        ),
      ),
    );
  }
}

class _PhotoCarousel extends StatefulWidget {
  final List<String> photoPaths;
  final ApiService api;
  const _PhotoCarousel({required this.photoPaths, required this.api});

  @override
  State<_PhotoCarousel> createState() => _PhotoCarouselState();
}

class _PhotoCarouselState extends State<_PhotoCarousel> {
  final _pageController = PageController();
  int _index = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<String>>(
      future: Future.wait(widget.photoPaths.map(widget.api.photoUrlAsync)),
      builder: (context, snap) {
        if (!snap.hasData) return const SizedBox(height: 200);
        final urls = snap.data!.where((u) => u.isNotEmpty).toList();
        if (urls.isEmpty) return const SizedBox.shrink();

        return Column(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox(
                height: 200,
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: urls.length,
                  onPageChanged: (i) => setState(() => _index = i),
                  itemBuilder: (context, i) => Image.network(
                    urls[i],
                    fit: BoxFit.cover,
                    width: double.infinity,
                    errorBuilder: (_, __, ___) => Container(color: Colors.grey.shade200),
                  ),
                ),
              ),
            ),
            if (urls.length > 1) ...[
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  urls.length,
                  (i) => Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i == _index ? AppColors.green : Colors.grey.shade300,
                    ),
                  ),
                ),
              ),
            ],
          ],
        );
      },
    );
  }
}
