class Announcement {
  final int id;
  final String title;
  final String content;
  final String date;
  final String type;

  Announcement({
    required this.id,
    required this.title,
    required this.content,
    required this.date,
    required this.type,
  });

  factory Announcement.fromJson(Map<String, dynamic> json) {
    return Announcement(
      id: json['id'],
      title: json['titulo'] ?? '',
      content: json['contenido'] ?? '',
      date: json['fecha'] ?? '',
      type: json['tipo'] ?? 'info',
    );
  }
}
