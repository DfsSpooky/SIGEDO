import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/teacher_data.dart';
import '../models/justification_type.dart';
import '../utils/constants.dart';

class ApiService {
  final Dio _dio = Dio(BaseOptions(baseUrl: AppConstants.baseUrl));
  final _storage = const FlutterSecureStorage();

  ApiService() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) {
          // Aquí podrías agregar lógica para refrescar token si es 401
          return handler.next(e);
        },
      ),
    );
  }

  Future<bool> login(String username, String password) async {
    try {
      final response = await _dio.post(
        AppConstants.loginEndpoint,
        data: {'username': username, 'password': password},
      );
      await _storage.write(key: 'access_token', value: response.data['access']);
      await _storage.write(
        key: 'refresh_token',
        value: response.data['refresh'],
      );
      return true;
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout || 
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionError) {
         throw Exception('Ocurrió un error de conexión con el servidor.');
      }
      if (e.response?.statusCode == 400 || e.response?.statusCode == 401) {
        final Map<String, dynamic> errorData = e.response?.data is String 
             ? jsonDecode(e.response?.data) 
             : e.response?.data;
        final String msg = errorData['message'] ?? 'Error en la solicitud';
        throw Exception(msg);
      }
      throw Exception('Error en el servidor: ${e.response?.statusCode}');
    } catch (e) {
      throw Exception('Error inesperado: $e');
    }
  }

  Future<void> logout() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<TeacherData> getTeacherStatus() async {
    final response = await _dio.get(AppConstants.statusEndpoint);
    return TeacherData.fromJson(response.data);
  }

  Future<void> markAttendance({
    required String actionType,
    required File photoFile,
    int? courseId,
    double? latitude,
    double? longitude,
  }) async {
    // 1. Convertir imagen a bytes
    List<int> imageBytes = await photoFile.readAsBytes();
    // 2. Base64 estándar
    String base64Image = base64Encode(imageBytes);
    // 3. Formato Data URI que espera Django
    String formattedBase64 = "data:image/jpeg;base64,$base64Image";

    final data = {
      "actionType": actionType,
      "photoBase64": formattedBase64,
      "courseId": courseId,
      "latitude": latitude,
      "longitude": longitude,
    };

    await _dio.post(AppConstants.attendanceEndpoint, data: data);
  }

  Future<bool> hasToken() async {
    final token = await _storage.read(key: 'access_token');
    return token != null;
  }
  Future<List<dynamic>> getSchedule() async {
    final response = await _dio.get(AppConstants.scheduleEndpoint);
    return response.data;
  }

  Future<Map<String, dynamic>> getNotifications() async {
    final response = await _dio.get(AppConstants.notificationsEndpoint);
    return response.data;
  }

  Future<bool> markNotificationAsRead(int notificationId) async {
    try {
      final response = await _dio.post('${AppConstants.baseUrl}/api/notificaciones/$notificationId/marcar-leida/');
      return response.statusCode == 200;
    } catch (e) {
      print("Error marking notification as read: $e");
      return false;
    }
  }

  // --- Justificaciones ---
  Future<List<JustificationType>> getJustificationTypes() async {
    final response = await _dio.get('${AppConstants.baseUrl}/api/tipo-justificaciones/');
    final List<dynamic> data = response.data;
    return data.map((json) => JustificationType.fromJson(json)).toList();
  }

  Future<void> createJustification({
    required int typeId,
    required DateTime startDate,
    required DateTime endDate,
    required String reason,
    required File file,
  }) async {
    // Convertir archivo a Base64
    List<int> fileBytes = await file.readAsBytes();
    String base64File = base64Encode(fileBytes);
    
    // Detectar extensión para el prefijo data URI (PDF o Imagen)
    String extension = file.path.split('.').last.toLowerCase();
    String mimeType = extension == 'pdf' ? 'application/pdf' : 'image/$extension';
    String formattedBase64 = "data:$mimeType;base64,$base64File";

    final data = {
      "tipo_id": typeId,
      "fecha_inicio": startDate.toIso8601String().split('T')[0],
      "fecha_fin": endDate.toIso8601String().split('T')[0],
      "motivo": reason,
      "documentoBase64": formattedBase64
    };

    await _dio.post('${AppConstants.baseUrl}/api/justificaciones/', data: data);
  }

  Future<void> updateFCMToken(String token) async {
    try {
      await _dio.post('${AppConstants.baseUrl}/api/mobile/fcm-token/', data: {'fcm_token': token});
    } catch (e) {
      print("Error actualizando FCM Token: $e");
      // No lanzamos error para no interrumpir el flujo del usuario
    }
  }

  Future<List<dynamic>> getDocuments() async {
    try {
      final response = await _dio.get('${AppConstants.baseUrl}/api/mobile/documents/');
      return response.data;
    } catch (e) {
      print('Error fetching documents: $e');
      return [];
    }
  }

  Future<bool> uploadDocument({required int typeId, required File file}) async {
    try {
      String fileName = file.path.split('/').last;
      
      FormData formData = FormData.fromMap({
        'tipo_id': typeId,
        'archivo': await MultipartFile.fromFile(file.path, filename: fileName),
      });

      final response = await _dio.post(
        '${AppConstants.baseUrl}/api/mobile/documents/upload/',
        data: formData,
      );

      return response.statusCode == 200;
    } catch (e) {
      print("Error uploading document: $e");
      return false;
    }
  }

  // --- Biometria ---
  Future<void> saveCredentials(String username, String password) async {
    await _storage.write(key: 'bio_username', value: username);
    await _storage.write(key: 'bio_password', value: password);
  }

  Future<bool> hasStoredCredentials() async {
    final username = await _storage.read(key: 'bio_username');
    final password = await _storage.read(key: 'bio_password');
    return username != null && password != null;
  }

  Future<Map<String, String>?> getStoredCredentials() async {
    if (!await hasStoredCredentials()) return null;
    final username = await _storage.read(key: 'bio_username');
    final password = await _storage.read(key: 'bio_password');
    return {'username': username!, 'password': password!};
  }

  // --- Recuperación de Contraseña ---
  Future<void> requestPasswordReset(String email) async {
    final response = await _dio.post(
      '${AppConstants.baseUrl}/api/auth/request-reset/',
      data: {'email': email},
    );
    // 200 OK significa enviado (o simulado si no existe)
  }

  Future<void> resetPassword({
    required String email,
    required String otp,
    required String newPassword,
  }) async {
    await _dio.post(
      '${AppConstants.baseUrl}/api/auth/reset-password/',
      data: {
        'email': email,
        'otp': otp,
        'new_password': newPassword,
      },
    );
  }
}
