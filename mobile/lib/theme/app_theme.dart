import 'package:flutter/material.dart';

class AppColors {
  static const green = Color(0xFF2E7D32);
  static const greenDark = Color(0xFF1B4D1E);
  static const greenLight = Color(0xFFE8F5E9);
  static const orange = Color(0xFFEF6C00);
  static const blue = Color(0xFF1565C0);
  static const red = Color(0xFFC62828);
  static const bg = Color(0xFFF7F8F7);

  // 회색 보조 텍스트/아이콘 공용 색상. 기존 Colors.grey.shade500(#9E9E9E)는 흰 배경
  // 대비 2.7:1로 WCAG AA 본문 텍스트 기준(4.5:1)에 크게 못 미쳐 618161로 교체했다
  // (흰 카드 대비 6.19:1, 페이지 배경 대비 5.82:1 - 어느 쪽 위에 있어도 AA를 만족).
  static const textSecondary = Color(0xFF616161);

  // 카드 테두리 / 하단 네비게이션 상단 구분선에 공용으로 쓰는 옅은 회색 - 기존
  // 인풋 테두리 색(#DDE2DD)과 같은 톤이라 새 색을 늘리지 않고 그대로 재사용한다.
  static const border = Color(0xFFDDE2DD);
}

const Map<String, Color> diagnosisTypeColors = {
  '병해': AppColors.red,
  '해충': AppColors.orange,
  '생리장애': AppColors.blue,
};

/// 지역 위험 신호등 다이얼로그에 쓰는 카테고리별 고정 안내문. DB(TreatmentReference)
/// 데이터를 참조하지 않는, 코드에 미리 박아둔 범용 문구다 - 신호등 응답에는 카테고리
/// (병해/해충/생리장애)만 오고 병명·건수는 절대 오지 않으므로, 특정 병해충을 짚어
/// 말하지 않는 이 수준의 일반 안내만 보여줄 수 있다.
const Map<String, String> regionalRiskCategoryAdvice = {
  '병해':
      '최근 잦은 강우나 높은 습도가 병해 확산의 주요 원인입니다. 배수로를 점검하고 통풍이 잘 되도록 해가림 상태를 확인해보세요. 발병 부위를 발견하면 즉시 제거해 확산을 막는 것이 중요합니다.',
  '해충': '기온이 오르면 해충 활동이 활발해집니다. 잎 뒷면과 새순 부위를 주기적으로 살펴보고, 끈끈이트랩으로 조기에 발견하는 것이 효과적입니다.',
  '생리장애': '최근 급격한 온도 변화나 불균형한 시비·관수가 원인일 수 있습니다. 최근 시비·관수 이력을 점검하고, 필요하면 토양 검정을 받아보세요.',
};

ThemeData buildAppTheme() {
  final base = ThemeData(
    useMaterial3: true,
    colorSchemeSeed: AppColors.green,
    scaffoldBackgroundColor: AppColors.bg,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.green,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: true,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.green,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.green, width: 1.5),
      ),
      // vertical 12는 Flutter의 InputDecorator 레이아웃 계산에서 입력창(드롭다운 포함)
      // 박스의 실제 세로 여유를 정하는 값이다 - 한글, 특히 받침 있는 글자는 라틴
      // 문자보다 렌더링에 필요한 세로 공간이 조금 더 커서, 이 값이 빠듯하면 드롭다운
      // 선택값 표시에서 글자 아랫부분(심하면 위아래 모두)이 잘려 보이는 게 실측
      // 확인됐다. 16으로 늘려 앱 전역 모든 입력창에 여유를 준다.
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
    ),
    // elevation 0(그림자 없음)이라 카드가 페이지 배경(#F7F8F7)과 거의 같은 흰색 위에
    // 놓이면 경계가 거의 안 보였다(명암비 1.06:1). 배경을 더 어둡게 하는 대신, 이미
    // 인풋에 쓰던 테두리 톤(AppColors.border)을 카드에도 그대로 둘러 구분되게 한다.
    cardTheme: CardTheme(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppColors.border, width: 1),
      ),
      margin: EdgeInsets.zero,
    ),
    // 비활성 탭 색(Colors.grey, #9E9E9E)이 흰 배경 대비 2.7:1로 텍스트 AA 기준
    // (4.5:1)은 물론 아이콘 기준(3:1)에도 못 미쳤다. AppColors.textSecondary로
    // 교체하고, 배경은 브랜드 그린을 옅게 tint한 AppColors.greenLight로 바꿔
    // 콘텐츠 영역과 색 자체로도 구분되게 한다(상단 구분선은 home_shell.dart에서 추가).
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      selectedItemColor: AppColors.green,
      unselectedItemColor: AppColors.textSecondary,
      backgroundColor: AppColors.greenLight,
      type: BottomNavigationBarType.fixed,
    ),
  );
}
