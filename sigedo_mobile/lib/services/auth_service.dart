import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../utils/constants.dart';

class AuthService {
  final Dio _dio = Dio(BaseOptions(baseUrl: AppConstants.baseUrl));
  final _storage = const FlutterSecureStorage();

  AuthService() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
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

  Future<bool> hasToken() async {
    final token = await _storage.read(key: 'access_token');
    return token != null;
  }

  Future<void> updateFCMToken(String token) async {
    try {
      await _dio.post('${AppConstants.baseUrl}/api/mobile/fcm-token/', data: {'fcm_token': token});
    } catch (e) {
      print("Error actualizando FCM Token: $e");
    }
  }

  // --- Biometria / Credenciales Guardadas ---
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
    await _dio.post(
      '${AppConstants.baseUrl}/api/auth/request-reset/',
      data: {'email': email},
    );
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
