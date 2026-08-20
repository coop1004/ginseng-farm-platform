import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../theme/app_theme.dart';

// 오인식 위험을 줄이기 위해 자유 발화 전체를 해석하지 않고, 이 두 그룹의 단어가
// 포함되어 있는지만 본다(정확히 일치할 필요 없음 - "네 저장해주세요"에도 매칭됨).
const _confirmWords = ['네', '맞아요', '맞아', '저장', '좋아요', '응', '확인'];
const _retryWords = ['아니요', '아니', '다시', '수정', '틀렸어요', '틀렸어'];
const _maxMisunderstandCount = 3;
const _confirmListenTimeout = Duration(seconds: 9);

enum _Stage {
  idle,
  permissionBlocked,
  recording,
  transcribing,
  review, // 텍스트 표시+TTS 읽어주기 및 음성확인 대기를 한 화면으로 합쳐서 보여준다.
  saving,
  saveFailed,
  unavailable,
}

/// 영농일지 "음성으로 입력" 전체 흐름(녹음 -> 변환 -> 읽어주기 -> 음성/터치 확인 -> 저장)을
/// 모달 시트로 보여준다. 모든 단계에 터치 대안이 있어 음성이 전혀 안 들려도 화면만 보고
/// 끝까지 완결할 수 있다. 실제 저장은 [onSaveRequested]로 위임해 호출부(work_log_form_screen)의
/// 기존 저장 로직(_api.createWorkLog 등)을 그대로 재사용한다.
Future<bool?> showVoiceNoteSheet(
  BuildContext context, {
  required void Function(String text) onTextRecognized,
  required Future<bool> Function(String text) onSaveRequested,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    isDismissible: true,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => _VoiceNoteSheet(onTextRecognized: onTextRecognized, onSaveRequested: onSaveRequested),
  );
}

class _VoiceNoteSheet extends StatefulWidget {
  final void Function(String text) onTextRecognized;
  final Future<bool> Function(String text) onSaveRequested;
  const _VoiceNoteSheet({required this.onTextRecognized, required this.onSaveRequested});

  @override
  State<_VoiceNoteSheet> createState() => _VoiceNoteSheetState();
}

class _VoiceNoteSheetState extends State<_VoiceNoteSheet> {
  final _speech = stt.SpeechToText();
  final _tts = FlutterTts();

  _Stage _stage = _Stage.idle;
  String _recognizedText = '';
  String? _localeId;
  bool _speechInitialized = false;
  bool _everHeardSpeechThisSession = false;
  int _misunderstandCount = 0;
  bool _voiceConfirmDisabled = false;
  bool _showSlowHint = false;
  bool _ttsSpeaking = false;
  Timer? _confirmTimeoutTimer;
  String? _saveError;
  String _unavailableMessage = '지금은 음성 입력을 쓸 수 없어요.';

  @override
  void initState() {
    super.initState();
    unawaited(_tts.awaitSpeakCompletion(true));
    unawaited(_tts.setLanguage('ko-KR'));
  }

  @override
  void dispose() {
    _confirmTimeoutTimer?.cancel();
    _speech.stop();
    _tts.stop();
    super.dispose();
  }

  Future<bool> _ensurePermission() async {
    final micStatus = await Permission.microphone.status;
    if (micStatus.isGranted) {
      unawaited(Permission.speech.request()); // iOS 음성인식 별도 권한 - 이미 허용된 경우도 조용히 재확인
      return true;
    }
    if (micStatus.isPermanentlyDenied) {
      if (mounted) setState(() => _stage = _Stage.permissionBlocked);
      return false;
    }
    // 시스템 권한 팝업이 뜨기 전에 맥락 설명 다이얼로그를 먼저 보여준다(고령 사용자가
    // 이유도 모르고 팝업만 보고 당황하지 않도록).
    if (!mounted) return false;
    final proceed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('음성 입력 안내'),
        content: const Text(
          '농작업 중에도 편하게 영농일지를 입력하실 수 있도록 음성인식을 사용합니다.\n다음 화면에서 마이크 권한을 허용해주세요.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('취소')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('확인')),
        ],
      ),
    );
    if (proceed != true) return false;

    final requested = await Permission.microphone.request();
    await Permission.speech.request();
    if (!requested.isGranted) {
      if (mounted) setState(() => _stage = _Stage.permissionBlocked);
      return false;
    }
    return true;
  }

  Future<void> _startRecording() async {
    _confirmTimeoutTimer?.cancel();
    setState(() {
      _saveError = null;
      _showSlowHint = false;
      _misunderstandCount = 0;
      _recognizedText = '';
    });

    if (!await _ensurePermission()) return;

    if (!_speechInitialized) {
      final ok = await _speech.initialize(onError: _handleRecordingError, onStatus: (_) {});
      _speechInitialized = ok;
      if (!ok) {
        if (mounted) setState(() => _stage = _Stage.unavailable);
        return;
      }
      final hasKorean = await _resolveKoreanLocale();
      if (!hasKorean) {
        if (mounted) {
          setState(() {
            _unavailableMessage = '이 기기에서는 음성인식을 지원하지 않습니다.';
            _stage = _Stage.unavailable;
          });
        }
        return;
      }
    }

    if (!mounted) return;
    setState(() => _stage = _Stage.recording);

    await _speech.listen(
      onResult: (result) {
        if (!mounted) return;
        setState(() => _recognizedText = result.recognizedWords);
        if (result.finalResult) _onRecordingFinished();
      },
      localeId: _localeId,
      listenOptions: stt.SpeechListenOptions(
        cancelOnError: true,
        partialResults: true,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
      ),
    );
  }

  /// 기기가 지원하는 로케일 목록에서 한국어 항목을 찾아 [_localeId]를 정확한 형식으로
  /// 맞춘다. 이전 코드는 이 값을 SpeechListenOptions 안에만 넣었는데, 실제로는 그 값이
  /// 사용되기 전에 목록 조회 자체가 비어 있거나 실패하면 _localeId가 null로 남아
  /// listen()이 기기 기본 로케일(한국어가 아닐 수 있음)로 인식을 시도하는 게 원인이었다.
  /// 그래서 먼저 표준값('ko_KR')으로 채워두고, 목록 조회가 성공하면 기기가 실제로
  /// 보고하는 정확한 ID로 덮어쓴다 - 목록 조회 자체는 됐는데 한국어가 정말 하나도 없는
  /// 경우에만 false를 반환해 음성인식 자체를 접게 한다.
  Future<bool> _resolveKoreanLocale() async {
    _localeId = 'ko_KR';
    try {
      final locales = await _speech.locales();
      if (locales.isEmpty) return true; // 목록 조회가 사실상 실패 - 표준값으로 시도
      final ko = locales.where((l) {
        final id = l.localeId.toLowerCase();
        return id == 'ko' || id.startsWith('ko_') || id.startsWith('ko-');
      });
      if (ko.isEmpty) return false; // 목록은 왔는데 한국어가 정말 없음
      _localeId = ko.first.localeId;
      return true;
    } catch (_) {
      return true; // 목록 조회 자체가 예외 - 표준값('ko_KR')으로 시도
    }
  }

  void _handleRecordingError(SpeechRecognitionError error) {
    if (!mounted || _stage != _Stage.recording) return;
    if (!_everHeardSpeechThisSession) {
      // 이번 시트를 연 뒤로 한 번도 인식된 적이 없다 - 기기/네트워크 문제로 보고
      // 반복 재시도를 강요하지 않고 키보드 입력으로 안내한다.
      setState(() => _stage = _Stage.unavailable);
    } else {
      setState(() => _stage = _Stage.idle);
    }
  }

  void _onRecordingFinished() {
    if (_recognizedText.trim().isEmpty) {
      setState(() => _stage = _Stage.idle);
      return;
    }
    _everHeardSpeechThisSession = true;
    widget.onTextRecognized(_recognizedText);
    setState(() => _stage = _Stage.transcribing);
    Future.delayed(const Duration(milliseconds: 300), _enterReviewAndSpeak);
  }

  Future<void> _enterReviewAndSpeak() async {
    if (!mounted) return;
    setState(() {
      _stage = _Stage.review;
      _ttsSpeaking = true;
    });
    // initState의 setLanguage는 await 없이 던져놓은 호출이라, 이 시점까진 충분한 시간이
    // 지났겠지만 확실히 하기 위해 첫 발화 직전에 한 번 더(idempotent) 확인해서 기다린다.
    await _tts.setLanguage('ko-KR');
    await _tts.speak('이렇게 입력하셨어요: $_recognizedText. 저장할까요?');
    if (!mounted) return;
    setState(() => _ttsSpeaking = false);
    if (!_voiceConfirmDisabled) _listenForConfirmation();
  }

  Future<void> _listenForConfirmation() async {
    if (!_speechInitialized || _stage != _Stage.review) return;
    _confirmTimeoutTimer?.cancel();
    _confirmTimeoutTimer = Timer(_confirmListenTimeout, () {
      if (!mounted || _stage != _Stage.review) return;
      setState(() => _showSlowHint = true);
      // 자동으로 취소하지 않고, 세션이 이미 끝나 있으면 계속 듣도록 다시 건다.
      if (!_speech.isListening) _listenForConfirmation();
    });
    await _speech.listen(
      onResult: (result) {
        if (!result.finalResult) return;
        _handleConfirmationSpeech(result.recognizedWords);
      },
      localeId: _localeId,
      listenOptions: stt.SpeechListenOptions(
        cancelOnError: true,
        partialResults: false,
        listenFor: const Duration(seconds: 10),
        pauseFor: const Duration(seconds: 3),
      ),
    );
  }

  void _handleConfirmationSpeech(String text) {
    if (_stage != _Stage.review) return;
    final normalized = text.replaceAll(' ', '');
    final isConfirm = _confirmWords.any((w) => normalized.contains(w));
    final isRetry = !isConfirm && _retryWords.any((w) => normalized.contains(w));
    if (isConfirm) {
      _confirmAndSave();
      return;
    }
    if (isRetry) {
      _retryRecording();
      return;
    }
    _misunderstandCount++;
    if (_misunderstandCount >= _maxMisunderstandCount) {
      _voiceConfirmDisabled = true;
      _confirmTimeoutTimer?.cancel();
      _tts.speak('음성 인식이 잘 안 되네요. 화면에서 직접 확인해주세요.');
      if (mounted) setState(() {});
    } else {
      _listenForConfirmation();
    }
  }

  void _retryRecording() {
    _confirmTimeoutTimer?.cancel();
    setState(() => _showSlowHint = false);
    _startRecording();
  }

  Future<void> _confirmAndSave() async {
    _confirmTimeoutTimer?.cancel();
    await _speech.stop();
    await _tts.stop();
    if (!mounted) return;
    setState(() {
      _stage = _Stage.saving;
      _saveError = null;
    });
    final ok = await widget.onSaveRequested(_recognizedText);
    if (!mounted) return;
    if (ok) {
      await _tts.speak('저장했습니다.');
      if (mounted) Navigator.of(context).pop(true);
    } else {
      setState(() {
        _stage = _Stage.saveFailed;
        _saveError = '저장에 실패했어요.';
      });
    }
  }

  void _close() => Navigator.of(context).pop(false);

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 14, 20, MediaQuery.of(context).viewInsets.bottom + 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 18),
            _buildContent(),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    switch (_stage) {
      case _Stage.idle:
        return _IdlePanel(onStart: _startRecording, onClose: _close);
      case _Stage.permissionBlocked:
        return _PermissionBlockedPanel(onOpenSettings: openAppSettings, onClose: _close);
      case _Stage.recording:
        return _RecordingPanel(text: _recognizedText, onStop: () => _speech.stop());
      case _Stage.transcribing:
        return const _TranscribingPanel();
      case _Stage.review:
        return _ReviewPanel(
          text: _recognizedText,
          speaking: _ttsSpeaking,
          voiceDisabled: _voiceConfirmDisabled,
          showSlowHint: _showSlowHint,
          onConfirm: _confirmAndSave,
          onRetry: _retryRecording,
        );
      case _Stage.saving:
        return const _SavingPanel();
      case _Stage.saveFailed:
        return _SaveFailedPanel(message: _saveError ?? '저장에 실패했어요.', onRetry: _confirmAndSave, onClose: _close);
      case _Stage.unavailable:
        return _UnavailablePanel(message: _unavailableMessage, onClose: _close);
    }
  }
}

class _IdlePanel extends StatelessWidget {
  final VoidCallback onStart;
  final VoidCallback onClose;
  const _IdlePanel({required this.onStart, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.mic_none_outlined, size: 56, color: AppColors.green),
        const SizedBox(height: 12),
        const Text('버튼을 누르고 말씀해주세요', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        const SizedBox(height: 20),
        ElevatedButton.icon(
          onPressed: onStart,
          icon: const Icon(Icons.mic),
          label: const Text('말하기 시작'),
          style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: onClose, child: const Text('취소하고 직접 입력하기')),
      ],
    );
  }
}

class _PermissionBlockedPanel extends StatelessWidget {
  final VoidCallback onOpenSettings;
  final VoidCallback onClose;
  const _PermissionBlockedPanel({required this.onOpenSettings, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.mic_off_outlined, size: 48, color: Colors.orange.shade800),
        const SizedBox(height: 12),
        const Text('마이크 권한이 꺼져 있어요', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text(
          '음성 입력을 쓰려면 나중에 설정에서 마이크 권한을 켜주세요.\n지금은 아래에서 직접 입력하실 수 있어요.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12.5, color: AppColors.textSecondary),
        ),
        const SizedBox(height: 20),
        OutlinedButton(onPressed: onOpenSettings, child: const Text('설정 열기')),
        const SizedBox(height: 8),
        ElevatedButton(onPressed: onClose, child: const Text('직접 입력하기')),
      ],
    );
  }
}

class _RecordingPanel extends StatelessWidget {
  final String text;
  final VoidCallback onStop;
  const _RecordingPanel({required this.text, required this.onStop});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.graphic_eq, size: 48, color: AppColors.green),
        const SizedBox(height: 8),
        const Text('듣고 있어요…', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          constraints: const BoxConstraints(minHeight: 60),
          decoration: BoxDecoration(color: AppColors.greenLight, borderRadius: BorderRadius.circular(10)),
          child: Text(text.isEmpty ? '…' : text, style: const TextStyle(fontSize: 14)),
        ),
        const SizedBox(height: 16),
        ElevatedButton.icon(
          onPressed: onStop,
          icon: const Icon(Icons.stop_circle_outlined),
          label: const Text('말하기 끝내기'),
          style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 4),
        const Text('말이 끝나면 자동으로도 멈춰요', style: TextStyle(fontSize: 11, color: AppColors.textSecondary)),
      ],
    );
  }
}

class _TranscribingPanel extends StatelessWidget {
  const _TranscribingPanel();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(height: 28, width: 28, child: CircularProgressIndicator(strokeWidth: 2.5)),
          SizedBox(height: 12),
          Text('변환 중이에요…', style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class _ReviewPanel extends StatelessWidget {
  final String text;
  final bool speaking;
  final bool voiceDisabled;
  final bool showSlowHint;
  final VoidCallback onConfirm;
  final VoidCallback onRetry;

  const _ReviewPanel({
    required this.text,
    required this.speaking,
    required this.voiceDisabled,
    required this.showSlowHint,
    required this.onConfirm,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(speaking ? Icons.volume_up : Icons.check_circle_outline, size: 20, color: AppColors.green),
            const SizedBox(width: 6),
            Text(speaking ? '읽어드리고 있어요…' : '이렇게 입력하셨어요',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: AppColors.greenLight, borderRadius: BorderRadius.circular(10)),
          child: Text(text, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        ),
        const SizedBox(height: 10),
        Text(
          voiceDisabled ? '아래 버튼으로 저장하거나 다시 말씀해주세요.' : '"네" 또는 "저장"이라고 말하거나, 아래 버튼을 눌러주세요.',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
        ),
        if (showSlowHint && !voiceDisabled) ...[
          const SizedBox(height: 4),
          Text('안 들리면 아래 버튼을 눌러주세요.',
              textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: Colors.orange.shade800, fontWeight: FontWeight.w600)),
        ],
        const SizedBox(height: 18),
        ElevatedButton.icon(
          onPressed: onConfirm,
          icon: const Icon(Icons.check),
          label: const Text('저장'),
          style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('다시 말하기'),
          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
        ),
      ],
    );
  }
}

class _SavingPanel extends StatelessWidget {
  const _SavingPanel();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(height: 28, width: 28, child: CircularProgressIndicator(strokeWidth: 2.5)),
          SizedBox(height: 12),
          Text('저장하는 중이에요…', style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class _SaveFailedPanel extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  final VoidCallback onClose;
  const _SaveFailedPanel({required this.message, required this.onRetry, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.error_outline, size: 44, color: AppColors.red),
        const SizedBox(height: 10),
        Text(message, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        ElevatedButton(onPressed: onRetry, child: const Text('다시 시도')),
        const SizedBox(height: 8),
        TextButton(onPressed: onClose, child: const Text('닫고 직접 저장하기')),
      ],
    );
  }
}

class _UnavailablePanel extends StatelessWidget {
  final String message;
  final VoidCallback onClose;
  const _UnavailablePanel({required this.message, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.mic_off_outlined, size: 44, color: Colors.grey.shade600),
        const SizedBox(height: 10),
        Text(message, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        const Text('직접 입력해주세요.', style: TextStyle(fontSize: 12.5, color: AppColors.textSecondary)),
        const SizedBox(height: 16),
        ElevatedButton(onPressed: onClose, child: const Text('확인')),
      ],
    );
  }
}
