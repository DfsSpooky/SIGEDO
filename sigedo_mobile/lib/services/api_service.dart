import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
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
          return handler.next(e);
        },
      ),
    );
  }

  // --- Dashboard & Asistencia ---

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
    List<int> imageBytes = await photoFile.readAsBytes();
    String base64Image = base64Encode(imageBytes);
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

  Future<List<dynamic>> getSchedule() async {
    final response = await _dio.get(AppConstants.scheduleEndpoint);
    return response.data;
  }

  // --- Notificaciones ---

  Future<Map<String, dynamic>> getNotifications() async {
    final response = await _dio.get(AppConstants.notificationsEndpoint);
    return response.data;
  }

  Future<bool> markNotificationAsRead(int notificationId) async {
    try {
      final response = await _dio.post(
        '${AppConstants.baseUrl}/api/notificaciones/$notificationId/marcar-leida/',
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint("Error marking notification as read: $e");
      return false;
    }
  }

  // --- Justificaciones ---

  Future<List<JustificationType>> getJustificationTypes() async {
    final response = await _dio.get(
      '${AppConstants.baseUrl}/api/tipo-justificaciones/',
    );
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
    String fileName = file.path.split('/').last;

    FormData formData = FormData.fromMap({
      "tipo_id": typeId,
      "fecha_inicio": startDate.toIso8601String().split('T')[0],
      "fecha_fin": endDate.toIso8601String().split('T')[0],
      "motivo": reason,
      "documento_adjunto": await MultipartFile.fromFile(
        file.path,
        filename: fileName,
      ),
    });

    await _dio.post(
      '${AppConstants.baseUrl}/api/justificaciones/',
      data: formData,
    );
  }

  // --- Documentos ---

  Future<List<dynamic>> getDocuments() async {
    try {
      final response = await _dio.get(
        '${AppConstants.baseUrl}/api/mobile/documents/',
      );
      return response.data;
    } catch (e) {
      debugPrint('Error fetching documents: $e');
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
      debugPrint("Error uploading document: $e");
      return false;
    }
  }

  // --- Recuperación de Contraseña ---

  Future<void> requestPasswordReset(String email) async {
    await _dio.post(
      AppConstants.passwordResetRequestEndpoint,
      data: {'email': email},
    );
  }

  Future<void> resetPassword({
    required String email,
    required String otp,
    required String newPassword,
  }) async {
    await _dio.post(
      AppConstants.passwordResetConfirmEndpoint,
      data: {'email': email, 'otp': otp, 'new_password': newPassword},
    );
  }

  // --- Adelanto de Clases ---

  Future<void> createClassAdvancement({
    required int courseId,
    required String reason,
  }) async {
    final data = {"courseId": courseId, "reason": reason};
    await _dio.post(
      '${AppConstants.baseUrl}/api/mobile/adelanto-clase/',
      data: data,
    );
  }

  // --- Director ---

  Future<List<dynamic>> getDirectorAttendanceFeed() async {
    try {
      final response = await _dio.get(
        '${AppConstants.baseUrl}/api/mobile/director/attendance/',
      );
      return response.data;
    } catch (e) {
      debugPrint("Error fetching director feed: $e");
      return [];
    }
  }

  Future<Map<String, dynamic>> getDirectorStats() async {
    try {
      final response = await _dio.get(
        '${AppConstants.baseUrl}/api/mobile/director/stats/',
      );
      return response.data;
    } catch (e) {
      debugPrint("Error fetching director stats: $e");
      return {};
    }
  }
}
