import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// 드롭다운 항목(DropdownMenuItem)에 쓰는 공용 텍스트 래퍼.
///
/// 이전엔 여기에 위아래 Padding + 줄 높이를 추가로 얹었었는데, 실제 원인은 항목 자체가
/// 아니라 InputDecorator의 contentPadding(앱 전역 테마, app_theme.dart)이 박스 높이를
/// 고정하는 데 있었다 - Flutter input_decorator.dart의 실제 레이아웃 계산에서
/// containerHeight가 부모가 준 maxHeight로 clamp되고, 그 안에서 다 못 들어간 내용은
/// overflow로 계산돼 그대로 잘린다. 항목 쪽에 내용을 더 키우면(패딩·줄높이 추가)
/// 오히려 필요한 높이만 늘어나 잘리는 양이 더 커지는 역효과가 났다 - 그래서 여기서는
/// 손대지 않고, 실제 박스 높이를 정하는 contentPadding 쪽을 늘리는 것으로 수정했다.
Widget dropdownItemText(
  String text, {
  TextStyle? style,
  TextOverflow overflow = TextOverflow.ellipsis,
  int maxLines = 1,
}) {
  return Text(
    text,
    overflow: overflow,
    maxLines: maxLines,
    style: style,
  );
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});
  @override
  Widget build(BuildContext context) => const Center(child: CircularProgressIndicator());
}

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 40, color: Colors.grey),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(onPressed: onRetry, child: const Text('다시 시도')),
            ],
          ],
        ),
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  final String message;
  final IconData icon;
  const EmptyView({super.key, required this.message, this.icon = Icons.inbox_outlined});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 40, color: Colors.grey.shade400),
          const SizedBox(height: 10),
          Text(message, style: const TextStyle(color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  final String title;
  final String? subtitle;
  const SectionTitle(this.title, {super.key, this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          if (subtitle != null) ...[
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                subtitle!,
                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
