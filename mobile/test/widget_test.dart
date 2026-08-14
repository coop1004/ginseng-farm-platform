import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ginseng_farm_app/main.dart';

void main() {
  testWidgets('로그인하지 않은 상태면 로그인 화면을 보여준다', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await initializeDateFormatting('ko_KR');
    await tester.pumpWidget(const GinsengFarmApp());
    await tester.pumpAndSettle();

    expect(find.text('인삼 AI 영농일지'), findsOneWidget);
    expect(find.text('로그인'), findsOneWidget);
    expect(find.text('계정이 없으신가요? 회원가입'), findsOneWidget);
  });
}
