import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/administrative_region.dart';
import '../models/crop.dart';
import '../models/farm.dart';
import '../providers/crop_provider.dart';
import '../services/api_service.dart';
import '../widgets/common.dart';

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
  late final TextEditingController _areaPyeong;
  late final TextEditingController _areaM2;
  late final TextEditingController _phone;
  late final TextEditingController _memo;

  String _facilityType = facilityTypes.first;
  int _cultivationYear = 1;
  DateTime? _cultivationStartDate;
  bool _cultivationStartDateEstimated = false;
  bool _saving = false;

  List<Crop> _crops = [];
  Crop? _selectedCrop;
  List<GrowthStage> _growthStages = [];
  int? _selectedGrowthStageId;
  bool _loadingCrops = true;

  List<AdministrativeRegion> _regions = [];
  int? _selectedRegionId;
  bool _loadingRegions = true;

  bool get _isEdit => widget.farm != null;
  bool get _isGinseng => _selectedCrop?.nameKr == '인삼';

  Crop? _findCrop(int? id) {
    if (id == null) return null;
    for (final c in _crops) {
      if (c.id == id) return c;
    }
    return null;
  }

  AdministrativeRegion? _findRegion(int? id) {
    if (id == null) return null;
    for (final r in _regions) {
      if (r.id == id) return r;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    final f = widget.farm;
    _farmName = TextEditingController(text: f?.farmName ?? '');
    _address = TextEditingController(text: f?.address ?? '');
    _areaPyeong = TextEditingController(text: f != null ? f.areaPyeong.toStringAsFixed(0) : '');
    _areaM2 = TextEditingController(text: f != null ? f.areaM2.toStringAsFixed(0) : '');
    _phone = TextEditingController(text: f?.phone ?? '');
    _memo = TextEditingController(text: f?.memo ?? '');
    _facilityType = f?.facilityType ?? facilityTypes.first;
    _cultivationYear = f?.cultivationYear ?? 1;
    _cultivationStartDate = f?.cultivationStartDate;
    _cultivationStartDateEstimated = f?.cultivationStartDateEstimated ?? false;
    _selectedGrowthStageId = f?.growthStageId;

    _areaPyeong.addListener(_syncAreaFromPyeong);
    _loadCrops();
    _loadRegions();
  }

  Future<void> _loadRegions() async {
    try {
      final regions = await _api.getRegions();
      final existingRegion = widget.farm?.region;
      int? initialId;
      if (existingRegion != null && existingRegion.isNotEmpty) {
        for (final r in regions) {
          if (r.sigungu == existingRegion) {
            initialId = r.id;
            break;
          }
        }
      }
      if (mounted) {
        setState(() {
          _regions = regions;
          _selectedRegionId = initialId;
          _loadingRegions = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loadingRegions = false);
    }
  }

  Future<void> _loadCrops() async {
    // 전체 작물이 아니라 이 농가가 등록한 작물 중에서만 고를 수 있다(CropProvider는 로그인
    // 시점에 이미 채워져 있으므로 네트워크 호출 없이 바로 읽는다).
    final crops = context.read<CropProvider>().myCrops;
    final existingCropId = widget.farm?.cropId;
    Crop? initial;
    for (final c in crops) {
      if (c.id == existingCropId) {
        initial = c;
        break;
      }
    }
    setState(() {
      _crops = crops;
      _selectedCrop = initial ?? (crops.isNotEmpty ? crops.first : null);
      _loadingCrops = false;
    });
    if (_selectedCrop != null && !_isGinseng) {
      await _loadGrowthStages(_selectedCrop!.id);
    }
  }

  Future<void> _loadGrowthStages(int cropId) async {
    try {
      final stages = await _api.getGrowthStages(cropId);
      if (mounted) setState(() => _growthStages = stages);
    } catch (_) {
      if (mounted) setState(() => _growthStages = []);
    }
  }

  void _onCropChanged(Crop? crop) {
    if (crop == null) return;
    setState(() {
      _selectedCrop = crop;
      _growthStages = [];
      _selectedGrowthStageId = null;
    });
    if (crop.nameKr != '인삼') {
      _loadGrowthStages(crop.id);
    }
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
    _areaPyeong.dispose();
    _areaM2.dispose();
    _phone.dispose();
    _memo.dispose();
    super.dispose();
  }

  Future<void> _pickCultivationStartDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _cultivationStartDate ?? now,
      firstDate: DateTime(now.year - 20),
      lastDate: now,
    );
    if (picked != null) {
      setState(() {
        _cultivationStartDate = picked;
        _cultivationStartDateEstimated = false; // 직접 고른 값이니 추정치 표시 해제
      });
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_isGinseng && _cultivationStartDate == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('정식일을 선택해주세요.')));
      return;
    }
    setState(() => _saving = true);
    try {
      final farm = Farm(
        id: widget.farm?.id ?? 0,
        householdId: widget.farm?.householdId ?? 0,
        cropId: _selectedCrop?.id,
        growthStageId: _isGinseng ? null : _selectedGrowthStageId,
        farmName: _farmName.text.trim(),
        address: _address.text.trim(),
        region: _findRegion(_selectedRegionId)?.sigungu,
        latitude: widget.farm?.latitude,
        longitude: widget.farm?.longitude,
        areaPyeong: double.tryParse(_areaPyeong.text) ?? 0,
        areaM2: double.tryParse(_areaM2.text) ?? 0,
        facilityType: _facilityType,
        cultivationYear: _cultivationYear,
        cultivationStartDate: _cultivationStartDate,
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
            if (_loadingCrops)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: LinearProgressIndicator(),
              )
            else if (_crops.isNotEmpty) ...[
              DropdownButtonFormField<int>(
                value: _selectedCrop?.id,
                isDense: false,
                itemHeight: null,
                decoration: const InputDecoration(labelText: '작물 *', prefixIcon: Icon(Icons.eco_outlined)),
                items: _crops
                    .map((c) => DropdownMenuItem(
                          value: c.id,
                          child: dropdownItemText(
                              '${c.iconEmoji ?? ''} ${c.nameKr}${c.isSampleData ? ' (샘플)' : ''}'.trim()),
                        ))
                    .toList(),
                onChanged: (id) => _onCropChanged(_findCrop(id)),
              ),
              const SizedBox(height: 12),
            ],
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
            if (_loadingRegions)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: LinearProgressIndicator(),
              )
            else
              DropdownButtonFormField<int>(
                value: _selectedRegionId,
                isExpanded: true,
                isDense: false,
                itemHeight: null,
                decoration: const InputDecoration(labelText: '지역(시/군/구)', prefixIcon: Icon(Icons.map_outlined)),
                items: _regions
                    .map((r) => DropdownMenuItem(
                          value: r.id,
                          child: dropdownItemText('${r.sido} ${r.sigungu}'),
                        ))
                    .toList(),
                onChanged: (id) => setState(() => _selectedRegionId = id),
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
              isDense: false,
              itemHeight: null,
              decoration: const InputDecoration(labelText: '시설구분', prefixIcon: Icon(Icons.roofing_outlined)),
              items: facilityTypes.map((t) => DropdownMenuItem(value: t, child: dropdownItemText(t))).toList(),
              onChanged: (v) => setState(() => _facilityType = v ?? _facilityType),
            ),
            const SizedBox(height: 12),
            // 인삼은 정식일을 저장해 재배연차를 자동계산하고, 그 외 작물은 실제
            // 생육단계(정식기/생육기 등)로 관리한다.
            if (_isGinseng) ...[
              InkWell(
                onTap: _pickCultivationStartDate,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: '정식일 *',
                    prefixIcon: Icon(Icons.event_outlined),
                    suffixIcon: Icon(Icons.edit_calendar_outlined),
                  ),
                  child: Text(_cultivationStartDate != null
                      ? '${_cultivationStartDate!.year}년 ${_cultivationStartDate!.month}월 ${_cultivationStartDate!.day}일'
                      : '선택해주세요'),
                ),
              ),
              if (_cultivationStartDate != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '재배 ${(DateTime.now().year - _cultivationStartDate!.year) + 1}년차로 계산됩니다.',
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  ),
                ),
              if (_cultivationStartDateEstimated)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '⚠ 기존 "N년근" 값으로 역산한 근사치입니다. 정확한 정식일로 다시 확인해주세요.',
                    style: TextStyle(fontSize: 11, color: Colors.orange.shade800, fontWeight: FontWeight.w600),
                  ),
                ),
            ] else if (_growthStages.isNotEmpty)
              DropdownButtonFormField<int>(
                value: _selectedGrowthStageId,
                isDense: false,
                itemHeight: null,
                decoration: const InputDecoration(labelText: '생육단계', prefixIcon: Icon(Icons.timeline_outlined)),
                items: _growthStages
                    .map((s) => DropdownMenuItem(value: s.id, child: dropdownItemText(s.nameKr)))
                    .toList(),
                onChanged: (v) => setState(() => _selectedGrowthStageId = v),
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
