import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:ginseng_farm_app/main.dart';

void main() {
  testWidgets('앱이 정상적으로 홈 화면을 렌더링한다', (WidgetTester tester) async {
    await initializeDateFormatting('ko_KR');
    await tester.pumpWidget(const GinsengFarmApp());
    await tester.pump();

    expect(find.text('홈'), findsOneWidget);
    expect(find.text('농장'), findsOneWidget);
    expect(find.text('영농일지'), findsOneWidget);
    expect(find.text('AI진단'), findsOneWidget);
    expect(find.text('통계'), findsOneWidget);
  });
}
