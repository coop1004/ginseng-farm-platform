import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/community.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class CommunityPostDetailScreen extends StatefulWidget {
  final int postId;
  const CommunityPostDetailScreen({super.key, required this.postId});

  @override
  State<CommunityPostDetailScreen> createState() => _CommunityPostDetailScreenState();
}

class _CommunityPostDetailScreenState extends State<CommunityPostDetailScreen> {
  final _api = ApiService();
  final _commentCtrl = TextEditingController();
  CommunityPost? _post;
  bool _loading = true;
  String? _error;
  bool _submittingComment = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final post = await _api.getCommunityPost(widget.postId);
      setState(() => _post = post);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _submitComment() async {
    final body = _commentCtrl.text.trim();
    if (body.isEmpty) return;
    setState(() => _submittingComment = true);
    try {
      await _api.createCommunityComment(postId: widget.postId, body: body);
      _commentCtrl.clear();
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('댓글 등록 실패: $e')));
    } finally {
      if (mounted) setState(() => _submittingComment = false);
    }
  }

  Future<void> _reportPost() async {
    final reason = await _promptReasonDialog(title: '이 게시글을 신고하시겠어요?');
    if (reason == null) return;
    try {
      await _api.reportCommunityPost(postId: widget.postId, reason: reason);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('신고가 접수되었습니다.')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('신고 실패: $e')));
    }
  }

  Future<void> _reportComment(int commentId) async {
    final reason = await _promptReasonDialog(title: '이 댓글을 신고하시겠어요?');
    if (reason == null) return;
    try {
      await _api.reportCommunityComment(commentId: commentId, reason: reason);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('신고가 접수되었습니다.')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('신고 실패: $e')));
    }
  }

  Future<String?> _promptReasonDialog({required String title}) async {
    final ctrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(labelText: '신고 사유(선택)'),
          maxLines: 2,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('취소')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('신고')),
        ],
      ),
    );
    if (confirmed != true) return null;
    return ctrl.text.trim().isEmpty ? null : ctrl.text.trim();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('게시글'),
        actions: [
          if (_post != null)
            IconButton(
              icon: const Icon(Icons.flag_outlined),
              tooltip: '신고하기',
              onPressed: _reportPost,
            ),
        ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: _error!, onRetry: _load)
              : _post == null
                  ? const SizedBox.shrink()
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
                      children: [
                        Text(_post!.title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Text(_post!.authorName, style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600, fontWeight: FontWeight.w700)),
                            const SizedBox(width: 8),
                            Text(DateFormat('yyyy.MM.dd HH:mm').format(_post!.createdAt), style: TextStyle(fontSize: 11.5, color: Colors.grey.shade400)),
                          ],
                        ),
                        const SizedBox(height: 14),
                        if (_post!.body != null && _post!.body!.isNotEmpty)
                          Text(_post!.body!, style: const TextStyle(fontSize: 14, height: 1.6)),
                        const SizedBox(height: 24),
                        const Divider(),
                        Text('댓글 ${_post!.comments.length}개', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                        const SizedBox(height: 10),
                        if (_post!.comments.isEmpty)
                          Text('아직 댓글이 없습니다.', style: TextStyle(color: Colors.grey.shade500, fontSize: 12.5))
                        else
                          ..._post!.comments.map((c) => _CommentTile(comment: c, onReport: () => _reportComment(c.id))),
                        const SizedBox(height: 16),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Expanded(
                              child: TextField(
                                controller: _commentCtrl,
                                decoration: const InputDecoration(hintText: '댓글을 입력하세요'),
                                minLines: 1,
                                maxLines: 3,
                              ),
                            ),
                            const SizedBox(width: 8),
                            IconButton(
                              onPressed: _submittingComment ? null : _submitComment,
                              icon: const Icon(Icons.send, color: AppColors.green),
                            ),
                          ],
                        ),
                      ],
                    ),
    );
  }
}

class _CommentTile extends StatelessWidget {
  final CommunityComment comment;
  final VoidCallback onReport;
  const _CommentTile({required this.comment, required this.onReport});

  @override
  Widget build(BuildContext context) {
    final badge = comment.authorType == 'consultant' ? '👤 컨설턴트' : '🌾 농가';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(badge, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.blue)),
              const SizedBox(width: 6),
              Text(comment.authorName, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text(DateFormat('MM.dd HH:mm').format(comment.createdAt), style: TextStyle(fontSize: 10.5, color: Colors.grey.shade400)),
              GestureDetector(
                onTap: onReport,
                child: Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Icon(Icons.flag_outlined, size: 14, color: Colors.grey.shade400),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(comment.body, style: const TextStyle(fontSize: 13, height: 1.4)),
        ],
      ),
    );
  }
}
