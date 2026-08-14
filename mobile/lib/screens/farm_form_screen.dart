import 'package:flutter/material.dart';

import '../models/farm.dart';
import '../services/api_service.dart';

class FarmFormScreen extends StatefulWidget {
  final Farm? farm;
  const FarmFormScreen({super.key, this.farm});

  @override
  State<FarmFormScreen> createState() => _FarmFormScreenState();
}

class _FarmFormScreenState extends State<FarmFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = ApiService();

  late final TextEditingController _farmName;
  late final TextEditingController _address;
  late final TextEditingController _region;
  late final TextEditingController _areaPyeong;
  late final TextEditingController _areaM2;
  late final TextEditingController _phone;
  late final TextEditingController _memo;

  String _facilityType = facilityTypes.first;
  int _cultivationYear = 1;
  bool _saving = false;

  bool get _isEdit => widget.farm != null;

  @override
  void initState() {
    super.initState();
    final f = widget.farm;
    _farmName = TextEditingController(text: f?.farmName ?? '');
    _address = TextEditingController(text: f?.address ?? '');
    _region = TextEditingController(text: f?.region ?? '');
    _areaPyeong = TextEditingController(text: f != null ? f.areaPyeong.toStringAsFixed(0) : '');
    _areaM2 = TextEditingController(text: f != null ? f.areaM2.toStringAsFixed(0) : '');
    _phone = TextEditingController(text: f?.phone ?? '');
    _memo = TextEditingController(text: f?.memo ?? '');
    _facilityType = f?.facilityType ?? facilityTypes.first;
    _cultivationYear = f?.cultivationYear ?? 1;

    _areaPyeong.addListener(_syncAreaFromPyeong);
  }

  void _syncAreaFromPyeong() {
    final pyeong = double.tryParse(_areaPyeong.text);
    if (pyeong != null) {
      final m2 = pyeong * 3.3058;
      _areaM2.text = m2.toStringAsFixed(0);
    }
  }

  @override
  void dispose() {
    _farmName.dispose();
    _address.dispose();
    _region.dispose();
    _areaPyeong.dispose();
    _areaM2.dispose();
    _phone.dispose();
    _memo.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final farm = Farm(
        id: widget.farm?.id ?? 0,
        householdId: widget.farm?.householdId ?? 0,
        farmName: _farmName.text.trim(),
        address: _address.text.trim(),
        region: _region.text.trim().isEmpty ? null : _region.text.trim(),
        latitude: widget.farm?.latitude,
        longitude: widget.farm?.longitude,
        areaPyeong: double.tryParse(_areaPyeong.text) ?? 0,
        areaM2: double.tryParse(_areaM2.text) ?? 0,
        facilityType: _facilityType,
        cultivationYear: _cultivationYear,
        phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
        memo: _memo.text.trim().isEmpty ? null : _memo.text.trim(),
        createdAt: widget.farm?.createdAt ?? DateTime.now(),
      );

      if (_isEdit) {
        await _api.updateFarm(widget.farm!.id, farm);
      } else {
        await _api.createFarm(farm);
      }

      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('저장 실패: $e')));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_isEdit ? '농장 정보 수정' : '농장 등록')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
          children: [
            TextFormField(
              controller: _farmName,
              decoration: const InputDecoration(labelText: '농장명 *', prefixIcon: Icon(Icons.storefront_outlined)),
              validator: (v) => (v == null || v.trim().isEmpty) ? '농장명을 입력해주세요.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _address,
              decoration: const InputDecoration(labelText: '지번(소재지) *', prefixIcon: Icon(Icons.place_outlined)),
              validator: (v) => (v == null || v.trim().isEmpty) ? '지번을 입력해주세요.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _region,
              decoration:
                  const InputDecoration(labelText: '지역(시/군)', hintText: '예: 금산, 풍기', prefixIcon: Icon(Icons.map_outlined)),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _areaPyeong,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: '면적(평) *'),
                    validator: (v) => (v == null || double.tryParse(v) == null) ? '숫자를 입력해주세요.' : null,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    controller: _areaM2,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: '면적(㎡)'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _facilityType,
              decoration: const InputDecoration(labelText: '시설구분', prefixIcon: Icon(Icons.roofing_outlined)),
              items: facilityTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
              onChanged: (v) => setState(() => _facilityType = v ?? _facilityType),
            ),
            const SizedBox(height: 12),
            Text('연차 (1~6년근)', style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700)),
            Wrap(
              spacing: 8,
              children: List.generate(6, (i) => i + 1)
                  .map((y) => ChoiceChip(
                        label: Text('$y년근'),
                        selected: _cultivationYear == y,
                        onSelected: (_) => setState(() => _cultivationYear = y),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: '연락처', prefixIcon: Icon(Icons.call_outlined)),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _memo,
              maxLines: 3,
              decoration: const InputDecoration(labelText: '메모', alignLabelWithHint: true),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : Text(_isEdit ? '수정 저장' : '농장 등록'),
            ),
          ],
        ),
      ),
    );
  }
}
