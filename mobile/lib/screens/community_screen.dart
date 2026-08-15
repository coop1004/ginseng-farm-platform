import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/community.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';
import 'community_post_detail_screen.dart';

class CommunityScreen extends StatefulWidget {
  const CommunityScreen({super.key});

  @override
  State<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends State<CommunityScreen> {
  final _api = ApiService();
  List<CommunityPost>? _posts;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final posts = await _api.getCommunityPosts();
      setState(() => _posts = posts);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('커뮤니티')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const LoadingView()
            : _error != null
                ? ErrorView(message: _error!, onRetry: _load)
                : (_posts == null || _posts!.isEmpty)
                    ? ListView(
                        children: [
                          const SizedBox(height: 80),
                          Center(
                            child: Text('아직 게시글이 없습니다.\n담당 컨설턴트의 공지를 기다려주세요.',
                                textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade500)),
                          ),
                        ],
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                        itemCount: _posts!.length,
                        itemBuilder: (context, i) => _PostCard(
                          post: _posts![i],
                          onTap: () async {
                            await Navigator.of(context)
                                .push(MaterialPageRoute(builder: (_) => CommunityPostDetailScreen(postId: _posts![i].id)));
                            _load();
                          },
                        ),
                      ),
      ),
    );
  }
}

class _PostCard extends StatelessWidget {
  final CommunityPost post;
  final VoidCallback onTap;
  const _PostCard({required this.post, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isChannel = post.kind == 'channel';
    final kindLabel = isChannel ? '📢 공지/팁' : post.kind == 'diagnosis_share' ? '🩺 진단 공유' : '게시글';
    final kindColor = isChannel ? AppColors.blue : AppColors.green;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(color: kindColor.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
                    child: Text(kindLabel, style: TextStyle(fontSize: 10.5, color: kindColor, fontWeight: FontWeight.w700)),
                  ),
                  const Spacer(),
                  Text(DateFormat('MM.dd').format(post.createdAt), style: TextStyle(fontSize: 11, color: Colors.grey.shade400)),
                ],
              ),
              const SizedBox(height: 8),
              Text(post.title, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800)),
              if (post.body != null && post.body!.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(post.body!, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: Colors.grey.shade700, height: 1.4)),
              ],
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(post.authorName, style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500, fontWeight: FontWeight.w600)),
                  const SizedBox(width: 8),
                  Icon(Icons.mode_comment_outlined, size: 13, color: Colors.grey.shade400),
                  const SizedBox(width: 2),
                  Text('${post.commentCount}', style: TextStyle(fontSize: 11.5, color: Colors.grey.shade500)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
