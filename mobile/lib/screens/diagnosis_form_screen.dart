import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/diagnosis.dart';
import '../models/farm.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../widgets/farm_selector.dart';
import 'diagnosis_result_screen.dart';

class DiagnosisFormScreen extends StatefulWidget {
  const DiagnosisFormScreen({super.key});

  @override
  State<DiagnosisFormScreen> createState() => _DiagnosisFormScreenState();
}

class _DiagnosisFormScreenState extends State<DiagnosisFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = ApiService();
  final _cropCtrl = TextEditingController(text: '인삼');

  Farm? _farm;
  String _type = diagnosisTypes.first;
  File? _photo;
  bool _analyzing = false;

  @override
  void initState() {
    super.initState();
    final farms = context.read<FarmProvider>().farms;
    if (farms.isNotEmpty) _farm = farms.first;
  }

  @override
  void dispose() {
    _cropCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, imageQuality: 90);
    if (picked != null) setState(() => _photo = File(picked.path));
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _farm == null) return;
    if (_photo == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('피해 부위 사진을 업로드해주세요.')));
      return;
    }
    setState(() => _analyzing = true);
    try {
      final result = await _api.createDiagnosis(
        farmId: _farm!.id,
        diagnosisType: _type,
        cropName: _cropCtrl.text.trim().isEmpty ? '인삼' : _cropCtrl.text.trim(),
        photo: _photo!,
      );
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => DiagnosisResultScreen(diagnosis: result, isNew: true)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('AI 진단 요청 실패: $e')));
      }
    } finally {
      if (mounted) setState(() => _analyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final farms = context.watch<FarmProvider>().farms;
    final today = DateTime.now();

    return Scaffold(
      appBar: AppBar(title: const Text('AI 병해충 · 생리장애 진단')),
      body: farms.isEmpty
          ? const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('먼저 농장을 등록해주세요.')))
          : AbsorbPointer(
              absorbing: _analyzing,
              child: Form(
                key: _formKey,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
                  children: [
                    FarmSelector(farms: farms, value: _farm, onChanged: (f) => setState(() => _farm = f)),
                    const SizedBox(height: 12),
                    Text('진단유형', style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 8,
                      children: diagnosisTypes
                          .map((t) => ChoiceChip(
                                label: Text(t),
                                selected: _type == t,
                                onSelected: (_) => setState(() => _type = t),
                              ))
                          .toList(),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _cropCtrl,
                      decoration: const InputDecoration(labelText: '작물명', prefixIcon: Icon(Icons.eco_outlined)),
                    ),
                    const SizedBox(height: 12),
                    InputDecorator(
                      decoration: const InputDecoration(labelText: '발생일자(자동입력)', prefixIcon: Icon(Icons.today_outlined)),
                      child: Text('${today.year}년 ${today.month}월 ${today.day}일'),
                    ),
                    const SizedBox(height: 16),
                    Text('피해 부위 사진 *', style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
                    const SizedBox(height: 6),
                    _PhotoBox(photo: _photo, onPick: _pickPhoto, onClear: () => setState(() => _photo = null)),
                    const SizedBox(height: 6),
                    Text(
                      '※ 사진에 GPS 위치정보가 포함되어 있으면 촬영 당시 기상 조건을 자동으로 분석에 반영합니다.',
                      style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: _analyzing ? null : _submit,
                      icon: _analyzing
                          ? const SizedBox(
                              height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.biotech_outlined),
                      label: Text(_analyzing ? 'AI 분석 중… (기상 데이터 조회 포함)' : 'AI 진단 시작'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}

class _PhotoBox extends StatelessWidget {
  final File? photo;
  final void Function(ImageSource) onPick;
  final VoidCallback onClear;

  const _PhotoBox({required this.photo, required this.onPick, required this.onClear});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Container(
            height: 200,
            width: double.infinity,
            color: Colors.grey.shade200,
            child: photo != null
                ? Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(photo!, fit: BoxFit.cover),
                      Positioned(
                        top: 6,
                        right: 6,
                        child: CircleAvatar(
                          backgroundColor: Colors.black54,
                          child: IconButton(icon: const Icon(Icons.close, color: Colors.white, size: 18), onPressed: onClear),
                        ),
                      ),
                    ],
                  )
                : const Center(child: Icon(Icons.add_a_photo_outlined, size: 40, color: Colors.grey)),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => onPick(ImageSource.camera),
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('사진 촬영'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => onPick(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('앨범 선택'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
