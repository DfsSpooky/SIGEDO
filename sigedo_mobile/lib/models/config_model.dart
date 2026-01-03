class PublicConfig {
  final String institutionName;
  final String? logoUrl;

  PublicConfig({required this.institutionName, this.logoUrl});

  factory PublicConfig.fromJson(Map<String, dynamic> json) {
    return PublicConfig(
      institutionName: json['nombre_institucion'] ?? 'Institución Educativa',
      logoUrl: json['logo'],
    );
  }
}
