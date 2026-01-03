class AppConstants {
  // Reemplaza con tu dominio de Ngrok o IP local
  // Para emulador Android usa: 'http://10.0.2.2:8000'
  static const String baseUrl =
      'https://oversophisticated-dedra-overgross.ngrok-free.dev';

  // Endpoints
  static const String loginEndpoint = '/api/token/';
  static const String statusEndpoint = '/api/mobile/status/';
  static const String attendanceEndpoint = '/api/mobile/attendance/';
  static const String scheduleEndpoint = '/api/horario-docente/';
  static const String notificationsEndpoint = '/api/notificaciones/json/';
  static const String passwordResetRequestEndpoint = '/api/password_reset/';
  static const String passwordResetConfirmEndpoint =
      '/api/password_reset/confirm/';
}
