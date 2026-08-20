import 'package:flutter/material.dart';

import '../models/farm.dart';

class FarmSelector extends StatelessWidget {
  final List<Farm> farms;
  final Farm? value;
  final ValueChanged<Farm?> onChanged;

  const FarmSelector({super.key, required this.farms, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
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
      decoration: const InputDecoration(labelText: '농장 선택', prefixIcon: Icon(Icons.grass)),
      items: farms
          .map((f) => DropdownMenuItem(
                value: f.id,
                child: Text('${f.farmName} (${f.address})', overflow: TextOverflow.ellipsis, maxLines: 1),
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
