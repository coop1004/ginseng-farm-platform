class CommunityComment {
  final int id;
  final int postId;
  final String authorType; // household / consultant / admin
  final String authorName;
  final String body;
  final String status;
  final DateTime createdAt;

  CommunityComment({
    required this.id,
    required this.postId,
    required this.authorType,
    required this.authorName,
    required this.body,
    required this.status,
    required this.createdAt,
  });

  factory CommunityComment.fromJson(Map<String, dynamic> json) {
    return CommunityComment(
      id: json['id'],
      postId: json['post_id'],
      authorType: json['author_type'] ?? 'household',
      authorName: json['author_name'] ?? '',
      body: json['body'] ?? '',
      status: json['status'] ?? 'visible',
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

class CommunityPost {
  final int id;
  final String title;
  final String? body;
  final List<String> photoPaths;
  final String kind; // channel / diagnosis_share / free
  final int? cropId;
  final String? cropName;
  final int? diagnosisId;
  final String visibility; // public / consultant_scope
  final String authorType;
  final String authorName;
  final String status;
  final int commentCount;
  final DateTime createdAt;
  final List<CommunityComment> comments;

  CommunityPost({
    required this.id,
    required this.title,
    this.body,
    this.photoPaths = const [],
    required this.kind,
    this.cropId,
    this.cropName,
    this.diagnosisId,
    required this.visibility,
    required this.authorType,
    required this.authorName,
    required this.status,
    this.commentCount = 0,
    required this.createdAt,
    this.comments = const [],
  });

  factory CommunityPost.fromJson(Map<String, dynamic> json) {
    return CommunityPost(
      id: json['id'],
      title: json['title'] ?? '',
      body: json['body'],
      photoPaths: (json['photo_paths'] as List<dynamic>? ?? []).map((e) => e as String).toList(),
      kind: json['kind'] ?? 'free',
      cropId: json['crop_id'],
      cropName: json['crop_name'],
      diagnosisId: json['diagnosis_id'],
      visibility: json['visibility'] ?? 'public',
      authorType: json['author_type'] ?? 'household',
      authorName: json['author_name'] ?? '',
      status: json['status'] ?? 'visible',
      commentCount: json['comment_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at']),
      comments: (json['comments'] as List<dynamic>? ?? []).map((e) => CommunityComment.fromJson(e)).toList(),
    );
  }
}
