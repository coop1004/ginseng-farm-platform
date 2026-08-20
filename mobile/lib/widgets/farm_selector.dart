import 'package:flutter/material.dart';

import '../models/farm.dart';
import 'common.dart';

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
      // 실제 원인: DropdownButtonFormField는 isDense 기본값이 true라, 닫힌 상태에서
      // 선택값을 그리는 내부 Container에 fontSize/iconSize 기준으로 계산한 고정
      // 높이(_denseButtonHeight, 보통 24px 안팎)가 강제된다. 이 값은 contentPadding,
      // TextStyle.height 배수, fontFamily 중 어느 것도 반영하지 않아서, 지금까지의
      // 시도(itemHeight, contentPadding 증감, height 2.0, fontFamily 교체)가 전부
      // 이 고정 높이 앞에서 무력했다. isDense:false로 끄면 이 고정 높이 대신 내용에
      // 맞춰 늘어나는 레이아웃을 쓰게 되어 글자가 잘리지 않는다.
      isDense: false,
      itemHeight: null,
      decoration: const InputDecoration(
        labelText: '농장 선택',
        prefixIcon: Icon(Icons.grass),
      ),
      items: farms
          .map((f) => DropdownMenuItem(
                value: f.id,
                child: dropdownItemText('${f.farmName} (${f.address})'),
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
