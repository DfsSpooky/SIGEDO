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
import '../services/notification_service.dart'; // Import NotificationService

import '../services/websocket_service.dart';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final AuthService _authService = AuthService();
  final NotificationService _notificationService =
      NotificationService(); // Instance

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
      await loadConfig(); // Cargar config institucional
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
        await loadConfig(); // Cargar config institucional
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

      // Programar Notificaciones Locales
      _scheduleLocalNotifications();

      notifyListeners();
    } catch (e) {
      debugPrint("Error cargando dashboard: $e");
      // Si falla al cargar dashboard (token expirado?), cerramos sesión
      if (e.toString().contains('401')) {
        await logout();
      }
    }
  }

  void _scheduleLocalNotifications() async {
    if (_teacherData == null) return;

    await _notificationService.cancelAll();
    final now = DateTime.now();

    for (var course in _teacherData!.courses) {
      // 1. Recordatorio 5 min antes de entrar
      if (course.startTime != null && !course.entryMarked) {
        final startDt = _parseToLocal(course.startTime!, now);
        if (startDt != null) {
          final scheduledTime = startDt.subtract(const Duration(minutes: 5));
          if (scheduledTime.isAfter(now)) {
            _notificationService.scheduleNotification(
              id: course.id * 100 + 1,
              title: "Clase por iniciar",
              body:
                  "Tu clase de ${course.name} comienza en 5 minutos en el aula ${course.classroom ?? 'S/N'}.",
              scheduledDate: scheduledTime,
            );
            debugPrint(
              "Scheduled Entry Notification for ${course.name} at $scheduledTime",
            );
          }
        }
      }

      // 2. Recordatorio 15 min después de SALIR (si olvidó marcar)
      // Ojo: Esto asume que la clase terminó y no marcó salida.
      if (course.endTime != null && !course.exitMarked) {
        final endDt = _parseToLocal(course.endTime!, now);
        if (endDt != null) {
          final scheduledTime = endDt.add(const Duration(minutes: 15));
          // Solo programar si todavía no ha pasado ese momento (o si estamos dentro del rango razonable?)
          // Si ya pasó hace 3 horas, no queremos notificar ahora.
          // Pero si estamos ANTES de endDt+15, lo programamos.
          if (scheduledTime.isAfter(now)) {
            _notificationService.scheduleNotification(
              id: course.id * 100 + 2,
              title: "¿Marcaste tu salida?",
              body:
                  "La clase de ${course.name} terminó hace 15 minutos. No olvides registrar tu salida.",
              scheduledDate: scheduledTime,
            );
            debugPrint(
              "Scheduled Exit Notification for ${course.name} at $scheduledTime",
            );
          }
        }
      }
    }
  }

  DateTime? _parseToLocal(String timeStr, DateTime referenceDate) {
    try {
      final parts = timeStr.split(':');
      final h = int.parse(parts[0]);
      final m = int.parse(parts[1]);
      return DateTime(
        referenceDate.year,
        referenceDate.month,
        referenceDate.day,
        h,
        m,
      );
    } catch (e) {
      return null;
    }
  }

  Future<void> markAttendance(
    String actionType,
    int? courseId, {
    File? photo,
    double? latitude,
    double? longitude,
    String? observation,
  }) async {
    try {
      await _apiService.markAttendance(
        actionType: actionType,
        photoFile: photo,
        courseId: courseId,
        latitude: latitude,
        longitude: longitude,
        observation: observation,
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
  Future<List<dynamic>> getJustifications() async {
    return await _apiService.getJustifications();
  }

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

  // --- Recuperación de Clases ---
  Future<List<dynamic>> getRecoveryRequests() async {
    return await _apiService.getRecoveryRequests();
  }

  Future<void> createRecoveryRequest({
    required int courseId,
    required DateTime dateToRecover,
    required DateTime proposedDate,
    required int durationMinutes,
    required String reason,
  }) async {
    await _apiService.createRecoveryRequest(
      courseId: courseId,
      dateToRecover: dateToRecover,
      proposedDate: proposedDate,
      durationMinutes: durationMinutes,
      reason: reason,
    );
  }

  // --- Perfil ---
  Future<void> updateProfile({String? phone, File? photo}) async {
    try {
      final response = await _apiService.updateProfile(
        phone: phone,
        photo: photo,
      );

      if (_teacherData != null && response['status'] == 'success') {
        final data = response['data'];
        _teacherData = _teacherData!.copyWith(
          teacher: _teacherData!.teacher.copyWith(
            phone: data['celular'],
            photoUrl: data['foto'],
          ),
        );
        notifyListeners();
      }
    } catch (e) {
      rethrow;
    }
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
