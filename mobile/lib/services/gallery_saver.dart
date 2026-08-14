import 'dart:io';

import 'package:image_gallery_saver_plus/image_gallery_saver_plus.dart';

/// 카메라로 찍은 사진을 서버 업로드와 별개로 기기 갤러리에도 남긴다.
/// 업로드가 최종 실패하더라도 사용자가 촬영한 사진 자체는 잃지 않도록 하기 위함이며,
/// 실패해도(권한 거부 등) 업로드 흐름을 막으면 안 되므로 항상 조용히 무시한다.
Future<void> saveToGalleryQuietly(File file) async {
  try {
    await ImageGallerySaverPlus.saveFile(file.path);
  } catch (_) {
    // 갤러리 저장은 부가 기능이므로 실패해도 무시
  }
}
