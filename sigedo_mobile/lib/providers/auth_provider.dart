import 'dart:io';
import 'package:flutter/material.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import '../models/teacher_data.dart';
import '../models/justification_type.dart';
import '../models/justification_type.dart';
import '../services/api_service.dart';
import '../services/biometric_service.dart';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();

  bool _isAuthenticated = false;
  bool _isLoading = false;
  TeacherData? _teacherData;
  String? _errorMessage;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  TeacherData? get teacherData => _teacherData;
  String? get errorMessage => _errorMessage;

  Future<void> checkAuthStatus() async {
    _isAuthenticated = await _apiService.hasToken();
    if (_isAuthenticated) {
      await loadDashboard();
    }
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final success = await _apiService.login(username, password);

      if (success) {
        _isAuthenticated = true;
        await loadDashboard();
      }
      return success;
    } catch (e) {
      if (e.toString().contains('Exception:')) {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
      } else {
        _errorMessage = "Ocurrió un error inesperado";
      }
      print("Login error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    try {
      await _apiService.logout();
    } catch (e) {
      print("Error limpiando storage: $e");
    } finally {
      _isAuthenticated = false;
      _teacherData = null;
      notifyListeners();
    }
  }

  Future<void> loadDashboard() async {
    try {
      _teacherData = await _apiService.getTeacherStatus();
      
      // Actualizar Token FCM en segundo plano
      FirebaseMessaging.instance.getToken().then((token) {
        if (token != null) _apiService.updateFCMToken(token);
      });

      notifyListeners();
    } catch (e) {
      print("Error cargando dashboard: $e");
      // Si falla al cargar dashboard (token expirado?), cerramos sesión
      if (e.toString().contains('401')) {
        await logout();
      }
    }
  }

  Future<void> markAttendance(
    String actionType,
    File photo,
    int? courseId, {
    double? latitude,
    double? longitude,
  }) async {
    try {
      await _apiService.markAttendance(
        actionType: actionType,
        photoFile: photo,
        courseId: courseId,
        latitude: latitude,
        longitude: longitude,
      );
      // Recargar datos para actualizar la UI (botones bloqueados)
      await loadDashboard();
    } catch (e) {
      throw e;
    }
  }

  // --- Justificaciones ---
  Future<List<JustificationType>> getJustificationTypes() async {
     return await _apiService.getJustificationTypes();
  }

  Future<void> createJustification({
    required int typeId,
    required DateTime startDate,
    required DateTime endDate,
    required String reason,
    required File file,
  }) async {
    await _apiService.createJustification(
      typeId: typeId,
      startDate: startDate,
      endDate: endDate,
      reason: reason,
      file: file,
    );
  }
  // --- Biometria ---
  final BiometricService _biometricService = BiometricService();

  Future<bool> isBiometricAvailable() async {
    return await _biometricService.isBiometricAvailable();
  }

  Future<bool> hasStoredCredentials() async {
    return await _apiService.hasStoredCredentials();
  }

  Future<void> saveCredentials(String username, String password) async {
    await _apiService.saveCredentials(username, password);
  }

  Future<bool> loginWithBiometrics() async {
    final authenticated = await _biometricService.authenticate();
    if (!authenticated) return false;

    final credentials = await _apiService.getStoredCredentials();
    if (credentials == null) return false;

    return await login(credentials['username']!, credentials['password']!);
  }
}
