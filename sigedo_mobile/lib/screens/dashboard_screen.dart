import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:ui'; // For ImageFilter
import '../providers/auth_provider.dart';
import '../models/teacher_data.dart';

import 'package:permission_handler/permission_handler.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import '../services/location_service.dart';
import 'credential_screen.dart';
import 'documents_screen.dart';
import 'justification_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Función auxiliar para saludos
  String get _greeting {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Buenos días';
    if (hour < 18) return 'Buenas tardes';
    return 'Buenas noches';
  }

  Future<void> _handleAttendance(String actionType, int? courseId) async {
    final scaffoldMessenger = ScaffoldMessenger.of(context);

    // 1. Permisos de Cámara
    var status = await Permission.camera.request();
    if (!status.isGranted) {
      if (mounted) {
        scaffoldMessenger.showSnackBar(
          const SnackBar(
            content: Text(
              'Se requiere permiso de cámara para marcar asistencia.',
            ),
          ),
        );
      }
      return;
    }

    // 2. Tomar Foto
    final ImagePicker picker = ImagePicker();
    final XFile? photo = await picker.pickImage(
      source: ImageSource.camera,
      preferredCameraDevice: CameraDevice.front,
      maxWidth: 600,
      imageQuality: 50,
    );

    if (photo == null) return; // Usuario canceló

    // 3. Enviar al API
    if (mounted) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => Center(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
            child: Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.9),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: Color(0xFF4F46E5)),
                  SizedBox(height: 16),
                  Text(
                    "Procesando...",
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      try {
        final locationService = LocationService();
        final position = await locationService.getCurrentLocation();

        // Usar AuthProvider y pasar File + Coordenadas
        await Provider.of<AuthProvider>(context, listen: false).markAttendance(
          actionType,
          File(photo.path), // Convertir XFile a File
          courseId,
          latitude: position.latitude,
          longitude: position.longitude,
        );

        if (mounted) {
          Navigator.pop(context); // Cerrar loader

          // Success Feedback
          showDialog(
            context: context,
            builder: (_) => AlertDialog(
              backgroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.check_circle, color: Colors.green, size: 60),
                  const SizedBox(height: 16),
                  Text(
                    "¡Éxito!",
                    style: GoogleFonts.outfit(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "Acción registrada correctamente.",
                    textAlign: TextAlign.center,
                    style: GoogleFonts.outfit(color: Colors.grey[600]),
                  ),
                ],
              ),
            ),
          );

          // Recargar datos
          Provider.of<AuthProvider>(context, listen: false).loadDashboard();
        }
      } catch (e) {
        if (mounted) {
          Navigator.pop(context);
          scaffoldMessenger.showSnackBar(
            SnackBar(
              content: Text('Error: $e'),
              backgroundColor: Colors.redAccent,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    final teacherInfo = auth.teacherData?.teacher;
    final dailyAttendance = auth.teacherData?.dailyAttendance;
    final courses = auth.teacherData?.courses ?? [];

    if (auth.isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: Color(0xFF4F46E5)),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6), // Light Grey Background
      body: RefreshIndicator(
        onRefresh: () => auth.loadDashboard(),
        color: const Color(0xFF4F46E5),
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: Column(
            children: [
              // --- HERO HEADER ---
              _buildHeroHeader(context, teacherInfo),

              // --- MAIN CONTENT OVERLAP ---
              Transform.translate(
                offset: const Offset(0, -40),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    children: [
                      // Daily Status Card (Glassmorphic)
                      _buildDailyStatusCard(context, dailyAttendance),

                      const SizedBox(height: 24),

                      // Quick Actions
                      _buildQuickActions(context),

                      const SizedBox(height: 24),

                      // Timeline Title
                      Row(
                        children: [
                          Container(
                            width: 4,
                            height: 24,
                            decoration: BoxDecoration(
                              color: const Color(0xFF4F46E5), // Indigo
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            "Tu Agenda de Hoy",
                            style: GoogleFonts.outfit(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: const Color(0xFF1F2937),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Courses List
                      if (courses.isEmpty)
                        _buildEmptyState(
                          context,
                          "No tienes clases programadas.\n¡Tómate un descanso!",
                        ),

                      ...courses.map(
                        (course) => _buildCourseTimelineItem(context, course),
                      ),

                      const SizedBox(height: 40),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeroHeader(BuildContext context, TeacherInfo? teacher) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.only(top: 60, bottom: 60, left: 24, right: 24),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Color(0xFF4F46E5),
            Color(0xFF818CF8),
          ], // Indigo to Light Indigo
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(36),
          bottomRight: Radius.circular(36),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _greeting,
                  style: GoogleFonts.outfit(
                    color: Colors.white.withOpacity(0.9),
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  teacher?.name ?? "Docente",
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.outfit(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    height: 1.1,
                  ),
                ),
              ],
            ),
          ),
          // Avatar with Glow
          Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.2),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: CircleAvatar(
              radius: 35,
              backgroundColor: Colors.white,
              child: Padding(
                padding: const EdgeInsets.all(2),
                child: CircleAvatar(
                  radius: 33,
                  backgroundImage: (teacher?.photoUrl != null)
                      ? NetworkImage(teacher!.photoUrl!)
                      : null,
                  backgroundColor: Colors.grey[200],
                  child: (teacher?.photoUrl == null)
                      ? const Icon(Icons.person, color: Colors.grey, size: 30)
                      : null,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDailyStatusCard(BuildContext context, DailyAttendance? daily) {
    bool isEntryMarked = daily?.entryMarked ?? false;
    bool isExitMarked = daily?.exitMarked ?? false;
    bool isCompleted = isEntryMarked && isExitMarked;

    Color startColor = isEntryMarked
        ? const Color(0xFF10B981)
        : const Color(0xFFF59E0B);

    if (isCompleted) {
      startColor = const Color(0xFF3B82F6);
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF4F46E5).withOpacity(0.15),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Stack(
          children: [
            // Decorative background circle
            Positioned(
              right: -20,
              top: -20,
              child: Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                  color: startColor.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            "Asistencia General",
                            style: GoogleFonts.outfit(
                              color: Colors.grey[500],
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0.5,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            isCompleted
                                ? "Jornada Finalizada"
                                : (isEntryMarked
                                      ? "En Jornada"
                                      : "Jornada Pendiente"),
                            style: GoogleFonts.outfit(
                              color: const Color(0xFF1F2937),
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: startColor.withOpacity(0.1),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          isCompleted
                              ? Icons.task_alt
                              : (isEntryMarked
                                    ? Icons.timer
                                    : Icons.access_time),
                          color: startColor,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Time Stats
                  Row(
                    children: [
                      _buildTimeStat(
                        "Entrada",
                        daily?.entryTime,
                        isEntryMarked,
                      ),
                      Container(
                        height: 30,
                        width: 1,
                        color: Colors.grey[200],
                        margin: const EdgeInsets.symmetric(horizontal: 20),
                      ),
                      _buildTimeStat("Salida", daily?.exitTime, isExitMarked),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // Action Button
                  if (!isCompleted)
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => _handleAttendance(
                          isEntryMarked ? "general_exit" : "general_entry",
                          null,
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: startColor,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          elevation: 4,
                          shadowColor: startColor.withOpacity(0.4),
                        ),
                        child: Text(
                          isEntryMarked ? "MARCAR SALIDA" : "MARCAR ENTRADA",
                          style: GoogleFonts.outfit(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            letterSpacing: 1,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeStat(String label, String? time, bool marked) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: GoogleFonts.outfit(color: Colors.grey[400], fontSize: 12),
        ),
        const SizedBox(height: 2),
        Text(
          marked ? (time ?? "--:--") : "--:--",
          style: GoogleFonts.outfit(
            color: const Color(0xFF1F2937),
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _buildQuickActionItem(
          context,
          icon: Icons.qr_code_scanner,
          label: "Carnet",
          color: const Color(0xFF6366F1),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const CredentialScreen()),
          ),
        ),
        _buildQuickActionItem(
          context,
          icon: Icons.folder_copy_outlined,
          label: "Docs",
          color: const Color(0xFFEC4899),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const DocumentsScreen()),
          ),
        ),
        _buildQuickActionItem(
          context,
          icon: Icons.assignment_late_outlined,
          label: "Justificar",
          color: const Color(0xFF14B8A6),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const JustificationScreen()),
          ),
        ),
      ],
    );
  }

  Widget _buildQuickActionItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.grey.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: GoogleFonts.outfit(
                  color: const Color(0xFF4B5563),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCourseTimelineItem(
    BuildContext context,
    CourseAttendance course,
  ) {
    bool inProgress = course.entryMarked && !course.exitMarked;
    bool completed = course.entryMarked && course.exitMarked;

    Color statusColor = const Color(0xFF6366F1); // Default Indigo
    if (inProgress) statusColor = const Color(0xFF10B981); // Green
    if (completed) statusColor = Colors.grey;

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline Line & Dot
          Column(
            children: [
              Container(
                width: 16,
                height: 16,
                decoration: BoxDecoration(
                  color: inProgress
                      ? Colors.white
                      : statusColor.withOpacity(0.2),
                  border: Border.all(
                    color: statusColor,
                    width: inProgress ? 4 : 2,
                  ),
                  shape: BoxShape.circle,
                ),
              ),
              Container(
                width: 2,
                height: 100, // Dynamic height ideal path, fixed for simplicity
                color: Colors.grey[200],
              ),
            ],
          ),
          const SizedBox(width: 16),

          // Card Content
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: inProgress
                    ? Border.all(
                        color: statusColor.withOpacity(0.3),
                        width: 1.5,
                      )
                    : null,
                boxShadow: [
                  BoxShadow(
                    color: Colors.grey.withOpacity(0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: statusColor.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          inProgress
                              ? "EN CURSO"
                              : (completed ? "FINALIZADO" : "PENDIENTE"),
                          style: GoogleFonts.outfit(
                            color: statusColor,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const Spacer(),
                      if (inProgress)
                        const Icon(
                          Icons.mic_none,
                          size: 16,
                          color: Colors.grey,
                        ), // Just an example decoration
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    course.name,
                    style: GoogleFonts.outfit(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFF1F2937),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Actions
                  Row(
                    children: [
                      if (!course.entryMarked)
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () =>
                                _handleAttendance("course_entry", course.id),
                            style: OutlinedButton.styleFrom(
                              side: BorderSide(color: statusColor),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            child: Text(
                              "Entrada",
                              style: GoogleFonts.outfit(
                                color: statusColor,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ),

                      if (inProgress) ...[
                        if (course.canMarkExit)
                          Expanded(
                            child: ElevatedButton(
                              onPressed: () =>
                                  _handleAttendance("course_exit", course.id),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: statusColor,
                                foregroundColor: Colors.white,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                padding: const EdgeInsets.symmetric(
                                  vertical: 12,
                                ),
                              ),
                              child: Text(
                                "Salida",
                                style: GoogleFonts.outfit(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          )
                        else
                          Expanded(
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                color: Colors.grey[50],
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: Colors.grey.shade200),
                              ),
                              child: Text(
                                "Salida ${course.exitTimeStr ?? '--:--'}",
                                style: GoogleFonts.outfit(
                                  color: Colors.grey[500],
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ),
                      ],

                      if (completed)
                        Text(
                          "Clase completada",
                          style: GoogleFonts.outfit(
                            color: Colors.grey[400],
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          children: [
            Opacity(
              opacity: 0.5,
              child: Image.asset(
                "assets/images/logo.png",
                width: 80,
                height: 80,
                errorBuilder: (_, __, ___) =>
                    const Icon(Icons.event_busy, size: 60, color: Colors.grey),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.outfit(color: Colors.grey[400], fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }
}
