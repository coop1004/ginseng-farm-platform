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
      decoration: const InputDecoration(labelText: '농장 선택', prefixIcon: Icon(Icons.grass)),
      items: farms
          .map((f) => DropdownMenuItem(
                value: f.id,
                child: Text('${f.farmName} (${f.address})', overflow: TextOverflow.ellipsis),
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
