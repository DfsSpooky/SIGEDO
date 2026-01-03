class JustificationType {
  final int id;
  final String nombre;

  JustificationType({required this.id, required this.nombre});

  factory JustificationType.fromJson(Map<String, dynamic> json) {
    return JustificationType(
      id: json['id'],
      nombre: json['nombre'],
    );
  }
}
