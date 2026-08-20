import 'package:flutter/material.dart';

import '../models/farm.dart';

class FarmSelector extends StatelessWidget {
  final List<Farm> farms;
  final Farm? value;
  final ValueChanged<Farm?> onChanged;

  const FarmSelector({super.key, required this.farms, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    // (B) 후보 수정 - TextStyle의 height를 명시적으로 크게 지정. titleMedium 기본값
    // (height: 1.50)을 기반으로 하되 2.0으로 올려서, "줄간격 자체가 부족해서 잘린다"는
    // 가설을 직접 겨냥해 검증한다. fontFamily는 건드리지 않는다(이번엔 height만으로
    // 해결되는지 먼저 확인하는 단계).
    final baseStyle = Theme.of(context).textTheme.titleMedium;
    final candidateStyle = baseStyle?.copyWith(height: 2.0) ?? const TextStyle(height: 2.0);

    return DropdownButtonFormField<int>(
      value: value?.id,
      // isExpanded 없이는 내부 Row가 mainAxisSize.min이라 Text에 폭 제약이 전혀
      // 없어져 overflow:ellipsis가 있어도 실제로는 잘리지 않고 화면 밖으로
      // 넘쳐(RenderFlex overflow) 버린다 - 긴 농장명("금산 3호 필지(스마트팜)")에서만
      // 드러나는 잠재 버그였다.
      isExpanded: true,
      // itemHeight를 null로 두면(기본값은 kMinInteractiveDimension=48) 각 항목이
      // 자기 내용에 맞는 높이로 그려진다 - 기본 48dp 고정 높이에서는 한글(특히 받침 있는
      // 글자)이 라틴 문자보다 실제로 필요한 세로 공간이 조금 더 커서, 선택된 값 표시
      // 영역에서 글자 아랫부분이 잘려 보이는 문제가 있었다.
      itemHeight: null,
      // (A) TEMP DIAGNOSTIC — 원인 확정 후 반드시 되돌릴 것: 필드 전체 영역을 빨간
      // 테두리로 표시해 실제 박스 경계가 어디인지 눈으로 확인한다.
      decoration: InputDecoration(
        labelText: '농장 선택',
        prefixIcon: const Icon(Icons.grass),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Colors.red, width: 3)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Colors.red, width: 3)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Colors.red, width: 3)),
      ),
      items: farms
          .map((f) => DropdownMenuItem(
                value: f.id,
                // (A) TEMP DIAGNOSTIC — 원인 확정 후 반드시 되돌릴 것: 텍스트 자체의
                // 실제 줄 박스 영역을 노란 배경으로 표시한다.
                child: Container(
                  color: Colors.yellow,
                  child: Text(
                    '${f.farmName} (${f.address})',
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                    style: candidateStyle, // (B) 후보 수정
                  ),
                ),
              ))
          .toList(),
      onChanged: (id) {
        final farm = farms.firstWhere((f) => f.id == id);
        onChanged(farm);
      },
      validator: (id) => id == null ? '농장을 선택해주세요.' : null,
    );
  }
}
