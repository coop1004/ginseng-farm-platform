import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../models/diagnosis.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

const _outcomeOptions = ['호전', '유지', '악화'];

/// 같은 진단에 이어 붙이는 방제 경과 기록 입력 화면. 사진은 선택사항(자가평가만
/// 남기는 것도 지원), outcome은 필수. 저장에 성공하면 true를 반환한다.
class DiagnosisFollowupScreen extends StatefulWidget {
  final int diagnosisId;
  final String? diagnosisLabel;
  final File? initialPhoto;

  const DiagnosisFollowupScreen({
    super.key,
    required this.diagnosisId,
    this.diagnosisLabel,
    this.initialPhoto,
  });

  @override
  State<DiagnosisFollowupScreen> createState() => _DiagnosisFollowupScreenState();
}

class _DiagnosisFollowupScreenState extends State<DiagnosisFollowupScreen> {
  final _api = ApiService();
  final _daysCtrl = TextEditingController();
  final _noteCtrl = TextEditingController();
  File? _photo;
  String? _outcome;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _photo = widget.initialPhoto;
  }

  @override
  void dispose() {
    _daysCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, imageQuality: 90);
    if (picked != null) setState(() => _photo = File(picked.path));
  }

  Future<void> _save() async {
    if (_outcome == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('경과(호전/유지/악화)를 선택해주세요.')));
      return;
    }
    setState(() => _saving = true);
    try {
      await _api.addDiagnosisFollowup(
        diagnosisId: widget.diagnosisId,
        outcome: _outcome!,
        note: _noteCtrl.text.trim().isEmpty ? null : _noteCtrl.text.trim(),
        daysSinceTreatment: int.tryParse(_daysCtrl.text.trim()),
        photo: _photo,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('경과 기록이 저장되었습니다.')));
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('경과 기록 저장 실패: $e')));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('경과 기록 추가')),
      body: AbsorbPointer(
        absorbing: _saving,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            if (widget.diagnosisLabel != null) ...[
              Text(widget.diagnosisLabel!, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
              const SizedBox(height: 16),
            ],
            Text('경과 사진 (선택)', style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _photo != null
                  ? Stack(
                      children: [
                        Image.file(_photo!, height: 180, width: double.infinity, fit: BoxFit.cover),
                        Positioned(
                          top: 6,
                          right: 6,
                          child: GestureDetector(
                            onTap: () => setState(() => _photo = null),
                            child: const CircleAvatar(
                              radius: 13,
                              backgroundColor: Colors.black54,
                              child: Icon(Icons.close, color: Colors.white, size: 16),
                            ),
                          ),
                        ),
                      ],
                    )
                  : Container(
                      height: 120,
                      width: double.infinity,
                      color: Colors.grey.shade200,
                      child: const Center(child: Icon(Icons.add_a_photo_outlined, size: 32, color: Colors.grey)),
                    ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickPhoto(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('사진 촬영'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickPhoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('앨범 선택'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Text('경과 *', style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              children: _outcomeOptions
                  .map((o) => ChoiceChip(
                        label: Text(o),
                        selected: _outcome == o,
                        onSelected: (_) => setState(() => _outcome = o),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _daysCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '방제 후 며칠째 (선택)', prefixIcon: Icon(Icons.event_repeat_outlined)),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _noteCtrl,
              maxLines: 3,
              decoration: const InputDecoration(labelText: '메모 (선택)', alignLabelWithHint: true),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.save_outlined),
              label: Text(_saving ? '저장 중…' : '경과 기록 저장'),
            ),
          ],
        ),
      ),
    );
  }
}

Color outcomeColor(String outcome) {
  switch (outcome) {
    case '호전':
      return AppColors.green;
    case '악화':
      return AppColors.red;
    default:
      return AppColors.orange;
  }
}

IconData outcomeIcon(String outcome) {
  switch (outcome) {
    case '호전':
      return Icons.trending_up;
    case '악화':
      return Icons.trending_down;
    default:
      return Icons.trending_flat;
  }
}

String outcomeBadgeLabel(String outcome) {
  switch (outcome) {
    case '호전':
      return '호전 중';
    case '악화':
      return '악화 주의';
    default:
      return '유지 중';
  }
}

/// DiagnosisPhotoEntry 하나(초기 사진 또는 경과 기록)를 타임라인 한 줄로 그린다.
class DiagnosisTimelineTile extends StatelessWidget {
  final DiagnosisPhotoEntry entry;
  final String Function(String? photoPath) photoUrl;

  const DiagnosisTimelineTile({super.key, required this.entry, required this.photoUrl});

  @override
  Widget build(BuildContext context) {
    final isFollowup = entry.phase == 'followup';
    final dateStr =
        '${entry.createdAt.year}.${entry.createdAt.month.toString().padLeft(2, '0')}.${entry.createdAt.day.toString().padLeft(2, '0')}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (entry.photoPath != null && entry.photoPath!.isNotEmpty)
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.network(photoUrl(entry.photoPath), width: 64, height: 64, fit: BoxFit.cover),
            )
          else
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(color: Colors.grey.shade200, borderRadius: BorderRadius.circular(10)),
              child: const Icon(Icons.notes_outlined, color: Colors.grey),
            ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      isFollowup ? '경과 기록' : '최초 등록 사진',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                    ),
                    const SizedBox(width: 6),
                    Text(dateStr, style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                  ],
                ),
                if (entry.outcome != null) ...[
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: outcomeColor(entry.outcome!).withOpacity(0.12),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      entry.outcome! + (entry.daysSinceTreatment != null ? ' · 방제 후 ${entry.daysSinceTreatment}일째' : ''),
                      style: TextStyle(fontSize: 11.5, color: outcomeColor(entry.outcome!), fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
                if (entry.note != null && entry.note!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(entry.note!, style: const TextStyle(fontSize: 12.5)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
