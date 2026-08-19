import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/farm.dart';
import '../models/work_log.dart';
import '../providers/crop_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_service.dart';
import '../services/gallery_saver.dart';
import '../widgets/farm_selector.dart';
import '../widgets/voice_note_sheet.dart';

class WorkLogFormScreen extends StatefulWidget {
  final WorkLog? log;
  const WorkLogFormScreen({super.key, this.log});

  @override
  State<WorkLogFormScreen> createState() => _WorkLogFormScreenState();
}

class _WorkLogFormScreenState extends State<WorkLogFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = ApiService();
  final _contentCtrl = TextEditingController();
  final _areaCtrl = TextEditingController();

  Farm? _farm;
  DateTime _date = DateTime.now();
  File? _photo;
  bool _saving = false;

  bool get _isEdit => widget.log != null;

  @override
  void initState() {
    super.initState();
    final activeCropId = context.read<CropProvider>().activeCrop?.id;
    final farms = context.read<FarmProvider>().forCrop(activeCropId);
    final log = widget.log;
    if (log != null) {
      _date = log.workDate;
      _contentCtrl.text = log.content;
      _areaCtrl.text = log.workAreaM2.toStringAsFixed(0);
      for (final f in farms) {
        if (f.id == log.farmId) {
          _farm = f;
          break;
        }
      }
    } else if (farms.isNotEmpty) {
      _farm = farms.first;
      _areaCtrl.text = _farm!.areaM2.toStringAsFixed(0);
    }
  }

  @override
  void dispose() {
    _contentCtrl.dispose();
    _areaCtrl.dispose();
    super.dispose();
  }

  void _onFarmChanged(Farm? farm) {
    setState(() {
      _farm = farm;
      _areaCtrl.text = (farm?.areaM2 ?? 0).toStringAsFixed(0); // 선택 농장 면적을 기본값으로 자동 입력
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2015),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, imageQuality: 85);
    if (picked != null) {
      final file = File(picked.path);
      setState(() => _photo = file);
      if (source == ImageSource.camera) unawaited(saveToGalleryQuietly(file));
    }
  }

  /// 실제 저장 호출만 담당하고 화면 전환은 하지 않는다 - 수동 "저장" 버튼과 음성 확인
  /// 완료 시점(voice_note_sheet) 양쪽에서 이 메서드 하나를 공유해서 쓴다.
  Future<bool> _performSave(String content) async {
    if (_farm == null) return false;
    setState(() => _saving = true);
    try {
      if (_isEdit) {
        await _api.updateWorkLog(
          id: widget.log!.id,
          workDate: _date,
          workAreaM2: double.tryParse(_areaCtrl.text) ?? _farm!.areaM2,
          content: content,
        );
      } else {
        await _api.createWorkLog(
          farmId: _farm!.id,
          workDate: _date,
          workAreaM2: double.tryParse(_areaCtrl.text) ?? _farm!.areaM2,
          content: content,
          photo: _photo,
        );
      }
      return true;
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('저장 실패: $e')));
      return false;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _farm == null) return;
    final ok = await _performSave(_contentCtrl.text.trim());
    if (ok && mounted) Navigator.of(context).pop(true);
  }

  Future<void> _openVoiceInput() async {
    if (_farm == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('먼저 농장을 선택해주세요.')));
      return;
    }
    final saved = await showVoiceNoteSheet(
      context,
      onTextRecognized: (text) {
        if (mounted) setState(() => _contentCtrl.text = text);
      },
      onSaveRequested: _performSave,
    );
    if (saved == true && mounted) Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final activeCropId = context.watch<CropProvider>().activeCrop?.id;
    final farms = context.watch<FarmProvider>().forCrop(activeCropId);

    return Scaffold(
      appBar: AppBar(title: Text(_isEdit ? '영농작업 기록 수정' : '영농작업 기록')),
      body: farms.isEmpty
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: Text('먼저 농장을 등록해주세요.')),
            )
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
                children: [
                  if (_isEdit)
                    _ExistingPhotoPreview(photoPath: widget.log!.photoPath, api: _api)
                  else
                    _PhotoPicker(photo: _photo, onPick: _pickPhoto, onClear: () => setState(() => _photo = null)),
                  const SizedBox(height: 16),
                  InkWell(
                    onTap: _pickDate,
                    child: InputDecorator(
                      decoration: const InputDecoration(labelText: '작업일자', prefixIcon: Icon(Icons.event_outlined)),
                      child: Text(DateFormat('yyyy년 MM월 dd일').format(_date)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (_isEdit)
                    InputDecorator(
                      decoration: const InputDecoration(labelText: '농장', prefixIcon: Icon(Icons.grass_outlined)),
                      child: Text(_farm?.farmName ?? '-'),
                    )
                  else
                    FarmSelector(farms: farms, value: _farm, onChanged: _onFarmChanged),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _areaCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: '작업면적(㎡)',
                      helperText: '선택한 농장의 면적이 자동 입력되며, 필요 시 수정할 수 있습니다.',
                      prefixIcon: Icon(Icons.square_foot_outlined),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: _contentCtrl,
                          maxLines: 5,
                          decoration: const InputDecoration(labelText: '작업내용 *', alignLabelWithHint: true),
                          validator: (v) => (v == null || v.trim().isEmpty) ? '작업내용을 입력해주세요.' : null,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: IconButton.filledTonal(
                          onPressed: _saving ? null : _openVoiceInput,
                          icon: const Icon(Icons.mic_outlined),
                          tooltip: '음성으로 입력',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: _saving ? null : _save,
                    child: _saving
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(_isEdit ? '수정 저장' : '작업기록 저장'),
                  ),
                ],
              ),
            ),
    );
  }
}

/// 수정 화면에서는 사진 교체를 지원하지 않고(범위 최소화), 기존 사진이 있으면
/// 읽기 전용으로만 보여준다.
class _ExistingPhotoPreview extends StatelessWidget {
  final String? photoPath;
  final ApiService api;
  const _ExistingPhotoPreview({required this.photoPath, required this.api});

  @override
  Widget build(BuildContext context) {
    if (photoPath == null || photoPath!.isEmpty) return const SizedBox.shrink();
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: FutureBuilder<String>(
        future: api.photoUrlAsync(photoPath),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return Container(height: 180, width: double.infinity, color: Colors.grey.shade200);
          }
          return Image.network(snapshot.data!, height: 180, width: double.infinity, fit: BoxFit.cover);
        },
      ),
    );
  }
}

class _PhotoPicker extends StatelessWidget {
  final File? photo;
  final void Function(ImageSource) onPick;
  final VoidCallback onClear;

  const _PhotoPicker({required this.photo, required this.onPick, required this.onClear});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Container(
            height: 180,
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
                : const Center(child: Icon(Icons.photo_camera_outlined, size: 40, color: Colors.grey)),
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
