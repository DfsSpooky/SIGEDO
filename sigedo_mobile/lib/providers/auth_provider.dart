import 'dart:io';
import 'package:flutter/material.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import '../models/teacher_data.dart';
import '../models/justification_type.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart'; // Import AuthService
import '../services/biometric_service.dart';
import '../utils/date_utils.dart';
import '../services/config_service.dart';
import '../models/config_model.dart';

import '../services/websocket_service.dart';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final AuthService _authService = AuthService(); // Use AuthService

  bool _isAuthenticated = false;
  bool _isLoading = false;
  TeacherData? _teacherData;
  String? _errorMessage;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  TeacherData? get teacherData => _teacherData;
  String? get errorMessage => _errorMessage;
  ApiService get api => _apiService;

  Future<void> checkAuthStatus() async {
    _isAuthenticated = await _authService.hasToken(); // Use AuthService
    if (_isAuthenticated) {
      await loadDashboard();
      _initWebSocket(); // Connect WS
    }
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final success = await _authService.login(
        username,
        password,
      ); // Use AuthService

      if (success) {
        _isAuthenticated = true;
        await loadDashboard();
        _initWebSocket(); // Connect WS
      }
      return success;
    } catch (e) {
      if (e.toString().contains('Exception:')) {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
      } else {
        _errorMessage = "Ocurrió un error inesperado";
      }
      debugPrint("Login error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    try {
      await _authService.logout(); // Use AuthService
    } catch (e) {
      debugPrint("Error limpiando storage: $e");
    } finally {
      _isAuthenticated = false;
      _teacherData = null;
      WebSocketService().disconnect(); // Close WS
      notifyListeners();
    }
  }

  Future<void> loadDashboard() async {
    try {
      _teacherData = await _apiService.getTeacherStatus();

      // Actualizar Token FCM en segundo plano
      FirebaseMessaging.instance.getToken().then((token) {
        if (token != null) {
          _authService.updateFCMToken(token); // Use AuthService
        }
      });

      notifyListeners();
    } catch (e) {
      debugPrint("Error cargando dashboard: $e");
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

      // Actualizar estado local INMEDIATAMENTE para feedback visual rápido
      _updateLocalState(actionType, courseId);
      notifyListeners();

      // Recargar datos para sincronizar completamente
      await loadDashboard();
    } catch (e) {
      rethrow;
    }
  }

  void _updateLocalState(String actionType, int? courseId) {
    if (_teacherData == null) return;

    final now = DateUtilsLima.now;
    final timeString = DateUtilsLima.formatTime(now);

    if (actionType == 'general_entry') {
      _teacherData = _teacherData!.copyWith(
        dailyAttendance: _teacherData!.dailyAttendance.copyWith(
          entryMarked: true,
          entryTime: timeString,
        ),
      );
    } else if (actionType == 'general_exit') {
      _teacherData = _teacherData!.copyWith(
        dailyAttendance: _teacherData!.dailyAttendance.copyWith(
          exitMarked: true,
          exitTime: timeString,
        ),
      );
    } else if (courseId != null) {
      final updatedCourses = _teacherData!.courses.map((course) {
        if (course.id == courseId) {
          if (actionType == 'course_entry') {
            return course.copyWith(
              entryMarked: true,
              // Asumimos que al marcar entrada NO se marca salida aún
            );
          } else if (actionType == 'course_exit') {
            return course.copyWith(exitMarked: true, exitTimeStr: timeString);
          }
        }
        return course;
      }).toList();

      _teacherData = _teacherData!.copyWith(courses: updatedCourses);
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
    return await _authService.hasStoredCredentials(); // Use AuthService
  }

  Future<void> saveCredentials(String username, String password) async {
    await _authService.saveCredentials(username, password); // Use AuthService
  }

  // --- Config Publica ---
  PublicConfig? _publicConfig;
  PublicConfig? get publicConfig => _publicConfig;

  Future<void> loadConfig() async {
    final configMap = await ConfigService.getInstitutionConfig();
    if (configMap != null) {
      _publicConfig = PublicConfig.fromJson(configMap);
      notifyListeners();
    }
  }

  Future<bool> loginWithBiometrics() async {
    final authenticated = await _biometricService.authenticate();
    if (!authenticated) return false;

    final credentials = await _authService.getStoredCredentials();
    if (credentials == null) return false;

    return await login(credentials['username']!, credentials['password']!);
  }

  // --- WebSocket Integration ---
  void _initWebSocket() async {
    try {
      final token = await _authService.getToken();
      if (token != null) {
        final wsService = WebSocketService();
        await wsService.connect(token);

        // Listen for updates
        wsService.stream?.listen((message) {
          debugPrint("AuthProvider received WS Message: $message");
          // Assuming 'type' field in JSON
          if (message['type'] == 'send_notification' ||
              message['type'] == 'attendance.update') {
            loadDashboard(); // Auto-refresh
          }
        });
      }
    } catch (e) {
      debugPrint("Error initializing WebSocket: $e");
    }
  }

  @override
  void dispose() {
    WebSocketService().disconnect();
    super.dispose();
  }
}
