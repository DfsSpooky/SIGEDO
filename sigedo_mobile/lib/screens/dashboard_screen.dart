import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:ui'; // For ImageFilter
import '../providers/auth_provider.dart';
import '../models/teacher_data.dart';
import '../utils/image_utils.dart'; // Import ImageUtils

import 'package:permission_handler/permission_handler.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import '../services/location_service.dart';
import 'credential_screen.dart';

import 'history_screen.dart';
import 'documents_screen.dart';

import '../utils/date_utils.dart';
import '../widgets/skeleton_loader.dart';
import '../widgets/announcement_carousel.dart';
import 'analytics_screen.dart';
import '../widgets/next_class_timer.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Función auxiliar para saludos
  String get _greeting {
    final hour = DateUtilsLima.now.hour;
    if (hour < 12) return 'Buenos días';
    if (hour < 18) return 'Buenas tardes';
    return 'Buenas noches';
  }

  Future<void> _handleAttendance(String actionType, int? courseId) async {
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final isExit = actionType.contains("exit");

    File? photoFile;
    String? observation;

    // 1. Flujo de ENTRADA (Requiere FOTO)
    if (!isExit) {
      // Permisos
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

      // Tomar Foto
      final ImagePicker picker = ImagePicker();
      final XFile? photo = await picker.pickImage(
        source: ImageSource.camera,
        preferredCameraDevice: CameraDevice.front,
        maxWidth: 600,
        imageQuality: 50,
      );

      if (photo == null) return; // Usuario canceló

      final File originalFile = File(photo.path);
      // Optimizar Imagen
      final compressedPhoto = await ImageUtils.compressImage(originalFile);
      photoFile = compressedPhoto ?? originalFile;
    }
    // 2. Flujo de SALIDA (Sin Foto, con Observación opcional)
    else {
      if (actionType == "course_exit") {
        final TextEditingController reasonCtrl = TextEditingController();
        bool? confirm = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: Text(
              "Marcar Salida",
              style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  "¿Desea marcar su salida del curso?",
                  style: GoogleFonts.outfit(color: Colors.grey[700]),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: reasonCtrl,
                  decoration: const InputDecoration(
                    labelText: "Observación / Motivo (Opcional)",
                    border: OutlineInputBorder(),
                    hintText: "Ej. Salida anticipada por...",
                  ),
                  maxLines: 2,
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text("Cancelar"),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4F46E5),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                child: const Text("Confirmar"),
              ),
            ],
          ),
        );
        if (confirm != true) return;
        observation = reasonCtrl.text.trim();
        if (observation.isEmpty) observation = null;
      } else {
        // Salida General - Confirmación simple
        bool? confirm = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: Text(
              "Finalizar Jornada",
              style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
            ),
            content: Text(
              "¿Está seguro que desea marcar su salida general?",
              style: GoogleFonts.outfit(color: Colors.grey[700]),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text("Cancelar"),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFEF4444),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                child: const Text("Finalizar"),
              ),
            ],
          ),
        );
        if (confirm != true) return;
      }
    }

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
                color: Colors.white.withValues(alpha: 0.9),
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

        if (!mounted) return;

        // Usar AuthProvider con parámetros nombrados
        await Provider.of<AuthProvider>(context, listen: false).markAttendance(
          actionType,
          courseId,
          photo: photoFile, // Use the potentially compressed photoFile
          latitude: position.latitude,
          longitude: position.longitude,
          observation: observation,
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
                      color: const Color(0xFF1F2937),
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
    // final dailyAttendance removed
    final courses = auth.teacherData?.courses ?? [];

    if (auth.isLoading) {
      return Scaffold(
        backgroundColor: const Color(0xFFF3F4F6),
        body: _buildSkeletonLoader(context),
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
                      // Announcements Carousel
                      if (auth.teacherData?.announcements.isNotEmpty ??
                          false) ...[
                        AnnouncementCarousel(
                          announcements: auth.teacherData!.announcements,
                        ),
                        const SizedBox(height: 24),
                      ],

                      // Daily Status Card (Glassmorphic)
                      _buildDailyStatusCard(context, auth.teacherData),

                      const SizedBox(height: 24),

                      // Next Class Countdown
                      _buildNextClassCard(context, courses),

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

                      ...List.generate(courses.length, (index) {
                        return _buildCourseTimelineItem(
                          context,
                          courses[index],
                          index == courses.length - 1,
                        );
                      }),

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
                    color: Colors.white.withValues(alpha: 0.9),
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
                  color: Colors.black.withValues(alpha: 0.2),
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

  Widget _buildDailyStatusCard(BuildContext context, TeacherData? data) {
    DailyAttendance? daily = data?.dailyAttendance;
    AttendanceConfig? config = data?.attendanceConfig;

    bool isEntryMarked = daily?.entryMarked ?? false;
    bool isExitMarked = daily?.exitMarked ?? false;
    bool isCompleted = isEntryMarked && isExitMarked;

    // --- Time Window Logic ---
    bool isButtonEnabled = true;
    String disabledMessage = "";

    // Only check time if we are trying to mark ENTRY (and entry is not marked yet)
    if (!isEntryMarked &&
        !isCompleted &&
        config?.generalEntryStartTime != null) {
      try {
        final now = DateTime.now();
        final parts = config!.generalEntryStartTime!.split(":");
        final startDt = DateTime(
          now.year,
          now.month,
          now.day,
          int.parse(parts[0]),
          int.parse(parts[1]),
        );

        if (now.isBefore(startDt)) {
          isButtonEnabled = false;
          disabledMessage = "Habilitado ${config.generalEntryStartTime}";
        }
      } catch (e) {
        debugPrint("Error parsing time: $e");
      }
    }
    // -------------------------

    // Define Theme Colors based on state
    Color primaryColor;
    Color accentColor;
    IconData statusIcon;
    String statusTitle;
    String statusMessage;

    if (isCompleted) {
      primaryColor = const Color(0xFF3B82F6); // Blue
      accentColor = const Color(0xFF60A5FA);
      statusIcon = Icons.verified_rounded;
      statusTitle = "Jornada Finalizada";
      statusMessage = "¡Excelente trabajo! Has completado tu jornada de hoy.";
    } else if (isEntryMarked) {
      primaryColor = const Color(0xFF10B981); // Emerald
      accentColor = const Color(0xFF34D399);
      statusIcon = Icons.business_center_rounded;
      statusTitle = "En Jornada";
      statusMessage = "Tu asistencia está activa. No olvides marcar tu salida.";
    } else {
      primaryColor = const Color(0xFFF59E0B); // Amber
      accentColor = const Color(0xFFFBBF24);
      statusIcon = Icons.wb_sunny_rounded;
      statusTitle = "Jornada Pendiente";
      statusMessage = "¡Hola! Marca tu entrada para comenzar el día.";
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: primaryColor.withValues(alpha: 0.15),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Stack(
          children: [
            // Decorative background gradients
            Positioned(
              right: -30,
              top: -30,
              child: Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    colors: [
                      primaryColor.withValues(alpha: 0.2),
                      primaryColor.withValues(alpha: 0.0),
                    ],
                  ),
                  shape: BoxShape.circle,
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // --- HEADER SECTION ---
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: primaryColor.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                "ASISTENCIA GENERAL",
                                style: GoogleFonts.outfit(
                                  color: primaryColor,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1.0,
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              statusTitle,
                              style: GoogleFonts.outfit(
                                color: const Color(0xFF1F2937),
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Dynamic Icon Container
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [primaryColor, accentColor],
                          ),
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: primaryColor.withValues(alpha: 0.3),
                              blurRadius: 10,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Icon(statusIcon, color: Colors.white, size: 28),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // --- PROGRESS BAR ---
                  // Visualizes Entry -> Exit flow
                  Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            "Progreso del día",
                            style: GoogleFonts.outfit(
                              color: Colors.grey[500],
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          Text(
                            isCompleted
                                ? "100%"
                                : (isEntryMarked ? "50%" : "0%"),
                            style: GoogleFonts.outfit(
                              color: primaryColor,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Container(
                        height: 8,
                        width: double.infinity,
                        decoration: BoxDecoration(
                          color: Colors.grey[100],
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Row(
                          children: [
                            AnimatedContainer(
                              duration: const Duration(milliseconds: 500),
                              curve: Curves.easeInOut,
                              width: isCompleted
                                  ? MediaQuery.of(context).size.width -
                                        88 // Approx full width minus padding
                                  : (isEntryMarked
                                        ? (MediaQuery.of(context).size.width -
                                                  88) *
                                              0.5
                                        : 0),
                              // Note: Precise width calculation is tricky inside Row, simplifying with FractionallySizedBox logic manually or LayoutBuilder
                              // Let's use Expanded for cleaner layout code:
                            ),
                          ],
                        ),
                      ),
                      // Better Progress Bar Implementation using Stack
                      Stack(
                        children: [
                          Container(
                            height: 8,
                            width: double.infinity,
                            decoration: BoxDecoration(
                              color: Colors.grey[100],
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                          LayoutBuilder(
                            builder: (context, constraints) {
                              return AnimatedContainer(
                                duration: const Duration(milliseconds: 800),
                                curve: Curves.fastOutSlowIn,
                                height: 8,
                                width:
                                    constraints.maxWidth *
                                    (isCompleted
                                        ? 1.0
                                        : (isEntryMarked ? 0.5 : 0.05)),
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    colors: [primaryColor, accentColor],
                                  ),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              );
                            },
                          ),
                        ],
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // --- INFO & TIMES ---
                  Row(
                    children: [
                      // Entry Time
                      Expanded(
                        child: _buildTimeStatNew(
                          "Entrada",
                          daily?.entryTime,
                          Icons.login_rounded,
                          isEntryMarked
                              ? const Color(0xFF10B981)
                              : Colors.grey[400]!,
                        ),
                      ),

                      // Divider
                      Container(
                        height: 40,
                        width: 1,
                        color: Colors.grey[200],
                        margin: const EdgeInsets.symmetric(horizontal: 16),
                      ),

                      // Exit Time
                      Expanded(
                        child: _buildTimeStatNew(
                          "Salida",
                          daily?.exitTime,
                          Icons.logout_rounded,
                          isExitMarked
                              ? const Color(0xFF3B82F6)
                              : Colors.grey[400]!,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // --- SMART TIP (Didactic Message) ---
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: primaryColor.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: primaryColor.withValues(alpha: 0.2),
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.tips_and_updates_outlined,
                          color: primaryColor,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            statusMessage,
                            style: GoogleFonts.outfit(
                              color: const Color(0xFF374151),
                              fontSize: 13,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Action Button (Only if not completed)
                  if (!isCompleted) ...[
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: isButtonEnabled
                            ? () => _handleAttendance(
                                isEntryMarked
                                    ? "general_exit"
                                    : "general_entry",
                                null,
                              )
                            : () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(
                                      "Registro disponible a partir de las ${config?.generalEntryStartTime}",
                                    ),
                                  ),
                                );
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: isButtonEnabled
                              ? primaryColor
                              : Colors.grey[400],
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 18),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          elevation: 8,
                          shadowColor: primaryColor.withValues(alpha: 0.4),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              isEntryMarked ? Icons.logout : Icons.login,
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              isEntryMarked
                                  ? "MARCAR SALIDA"
                                  : (isButtonEnabled
                                        ? "MARCAR ENTRADA"
                                        : disabledMessage),
                              style: GoogleFonts.outfit(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeStatNew(
    String label,
    String? time,
    IconData icon,
    Color color,
  ) {
    bool hasTime = time != null;
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: GoogleFonts.outfit(
                color: Colors.grey[500],
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
            Text(
              hasTime ? time : "--:--",
              style: GoogleFonts.outfit(
                color: hasTime ? const Color(0xFF1F2937) : Colors.grey[400],
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Row(
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
        if (Provider.of<AuthProvider>(context).teacherData?.teacher.isStaff ??
            false)
          _buildQuickActionItem(
            context,
            icon: Icons.analytics_outlined,
            label: "Monitorear",
            color: const Color(0xFFF59E0B),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DirectorAnalyticsScreen(),
              ),
            ),
          ),
        _buildQuickActionItem(
          context,
          icon: Icons.history_rounded,
          label: "Historial",
          color: const Color(0xFF8B5CF6),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const HistoryScreen()),
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
                color: Colors.grey.withValues(alpha: 0.05),
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
                  color: color.withValues(alpha: 0.1),
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

  Future<void> _showAdelantoDialog(CourseAttendance course) async {
    final TextEditingController reasonController = TextEditingController();
    await showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(
          "Adelantar Clase",
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Falta más de 10 minutos para el inicio. ¿Desea adelantar el inicio de la clase?",
              style: GoogleFonts.outfit(color: Colors.grey[700]),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: reasonController,
              decoration: const InputDecoration(
                labelText: "Motivo (Opcional)",
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text("Cancelar"),
          ),
          ElevatedButton(
            onPressed: () async {
              final reason = reasonController.text.trim();

              // Show Loading (pushing a new dialog on top of the current one)
              // Actually, better to just disable button or show loading indicator.
              // But assuming we want to keep logic:
              // Original code didn't show loading dialog explicitly here, it just called API.
              // Wait, previous code had `Navigator.pop(context); // Close Loading`...
              // Was there a loading dialog? The code viewed didn't show one being pushed.
              // Ah, looking at line 645 `await showDialog`.
              // The logic is:
              // 1. Call API.
              // 2. Pop the Adelanto Dialog.
              // 3. Refresh Dashboard.
              // 4. Show SnackBar.

              try {
                // Use screen context for Provider
                await Provider.of<AuthProvider>(
                  context, // screen context
                  listen: false,
                ).api.createClassAdvancement(
                  courseId: course.id,
                  reason: reason,
                );

                if (!dialogContext.mounted) return;
                Navigator.pop(dialogContext); // Close Adelanto Dialog

                if (!mounted) return; // Check screen mounted

                // Refresh to unlock Entry button
                await Provider.of<AuthProvider>(
                  context, // screen context
                  listen: false,
                ).loadDashboard();

                if (!mounted) return;

                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text("Adelanto registrado. Puede marcar entrada."),
                  ),
                );
              } catch (e) {
                if (!mounted) return; // Prioritize screen context for SnackBar
                // Using dialogContext to pop? If it failed, do we close dialog?
                // Use dialogContext.mounted check?
                if (dialogContext.mounted) {
                  Navigator.pop(dialogContext);
                }

                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text("Error: $e")));
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4F46E5),
              foregroundColor: Colors.white,
            ),
            child: const Text("Confirmar"),
          ),
        ],
      ),
    );
  }

  Widget _buildNextClassCard(
    BuildContext context,
    List<CourseAttendance> courses,
  ) {
    // 1. Calculate Next Class
    final now = DateUtilsLima.now;
    CourseAttendance? nextCourse;
    DateTime? nextStartTime;
    // int minutesRemaining = 0; // Removed as it is unused

    for (var course in courses) {
      if (course.entryMarked) continue; // Already started/done

      final start = DateUtilsLima.parseTimeString(course.startTime);
      if (start == null) continue;

      // Check if it's in the future
      if (start.isAfter(now)) {
        // If it's the first one we find or earlier than current candidate
        if (nextStartTime == null || start.isBefore(nextStartTime)) {
          nextCourse = course;
          nextStartTime = start;
          // minutesRemaining = start.difference(now).inMinutes; // Removed
        }
      }
    }

    if (nextCourse == null) return const SizedBox.shrink();

    // 2. Build Card using new Widget
    return NextClassTimer(course: nextCourse);
  }

  Widget _buildCourseTimelineItem(
    BuildContext context,
    CourseAttendance course,
    bool isLast,
  ) {
    bool inProgress = course.entryMarked && !course.exitMarked;
    bool completed = course.entryMarked && course.exitMarked;

    // Future course check could be better if backend sent it,
    // but we can infer if not marked and no entry time.
    bool isFuture = !course.entryMarked;

    Color statusColor = const Color(0xFF6366F1); // Default Indigo
    if (inProgress) statusColor = const Color(0xFF10B981); // Green
    if (completed) statusColor = Colors.grey;

    return Container(
      margin: const EdgeInsets.only(
        bottom: 0,
      ), // Removed margin, managed by Column/Stack if needed
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Timeline Line & Dot
            SizedBox(
              width: 24,
              child: Column(
                children: [
                  // Dot
                  Container(
                    width: 16,
                    height: 16,
                    decoration: BoxDecoration(
                      color: inProgress
                          ? Colors.white
                          : (isFuture
                                ? Colors.white
                                : statusColor.withValues(alpha: 0.2)),
                      border: Border.all(
                        color: isFuture ? Colors.grey[300]! : statusColor,
                        width: inProgress ? 4 : 2,
                      ),
                      shape: BoxShape.circle,
                    ),
                    child: inProgress
                        ? Center(
                            child: Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: statusColor,
                                shape: BoxShape.circle,
                              ),
                            ),
                          )
                        : null,
                  ),
                  // Line
                  if (!isLast)
                    Expanded(
                      child: Container(
                        width: 2,
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        decoration: BoxDecoration(
                          color: isFuture
                              ? Colors.transparent
                              : statusColor.withValues(
                                  alpha: 0.2,
                                ), // Solid for past
                          border: isFuture
                              ? Border.symmetric(
                                  vertical: BorderSide(
                                    color: Colors.grey[300]!,
                                    width: 1,
                                    style: BorderStyle.none,
                                  ),
                                )
                              : null, // Dashed replacement hack or just grey
                          // Simple solid grey line for future for now to keep it clean, or custom dashed painter.
                          // Let's use a simple Grey line for future.
                          gradient: isFuture
                              ? LinearGradient(
                                  begin: Alignment.topCenter,
                                  end: Alignment.bottomCenter,
                                  colors: [
                                    Colors.grey[300]!,
                                    Colors.grey[200]!,
                                  ],
                                  stops: const [0.0, 0.5],
                                )
                              : null,
                        ),
                        // Dashed line implementation requires CustomPainter, keeping it simple solid grey for future.
                        child: isFuture
                            ? LayoutBuilder(
                                builder: (context, constraints) {
                                  return Flex(
                                    direction: Axis.vertical,
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceBetween,
                                    children: List.generate(
                                      (constraints.maxHeight / 6).floor(),
                                      (index) => SizedBox(
                                        width: 2,
                                        height: 3,
                                        child: DecoratedBox(
                                          decoration: BoxDecoration(
                                            color: Colors.grey[300],
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                },
                              )
                            : null,
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 16),

            // Card Content
            Expanded(
              child: Padding(
                // Pricing padding for the card to separate from line
                padding: const EdgeInsets.only(bottom: 24),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: inProgress
                        ? Border.all(
                            color: statusColor.withValues(alpha: 0.3),
                            width: 1.5,
                          )
                        : Border.all(color: Colors.transparent),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.grey.withValues(alpha: 0.05),
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
                              color: isFuture
                                  ? Colors.grey[100]
                                  : statusColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              inProgress
                                  ? "EN CURSO"
                                  : (completed ? "FINALIZADO" : "PENDIENTE"),
                              style: GoogleFonts.outfit(
                                color: isFuture
                                    ? Colors.grey[500]
                                    : statusColor,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const Spacer(),
                          // Classroom Badge
                          if (course.classroom != null) ...[
                            Icon(
                              Icons.location_on_outlined,
                              size: 14,
                              color: Colors.grey[400],
                            ),
                            const SizedBox(width: 4),
                            Text(
                              course.classroom!,
                              style: GoogleFonts.outfit(
                                color: Colors.grey[600],
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        course.name,
                        style: GoogleFonts.outfit(
                          fontSize: 15,
                          fontWeight: isFuture
                              ? FontWeight.w500
                              : FontWeight.bold,
                          color: isFuture
                              ? Colors.grey[600]
                              : const Color(0xFF1F2937),
                        ),
                      ),
                      if (course.specialty != null &&
                          course.specialty!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2, bottom: 2),
                          child: Text(
                            course.specialty!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.outfit(
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                              color: Colors.grey[500],
                            ),
                          ),
                        ),
                      if (course.startTime != null &&
                          course.endTime != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          "${course.startTime} - ${course.endTime}",
                          style: GoogleFonts.outfit(
                            fontSize: 13,
                            color: Colors.grey[400],
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],

                      const SizedBox(height: 10), // Reduced from 16
                      // Actions
                      Row(
                        children: [
                          if (!course.entryMarked)
                            Builder(
                              builder: (context) {
                                bool canMark = true;
                                final start = DateUtilsLima.parseTimeString(
                                  course.startTime,
                                );
                                final now = DateUtilsLima.now;

                                if (start != null) {
                                  // 10 minute rule
                                  final diff = start.difference(now).inMinutes;
                                  if (diff > 10) canMark = false;
                                }

                                if (canMark) {
                                  return Expanded(
                                    child: OutlinedButton(
                                      onPressed: () => _handleAttendance(
                                        "course_entry",
                                        course.id,
                                      ),
                                      style: OutlinedButton.styleFrom(
                                        side: BorderSide(color: statusColor),
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(
                                            12,
                                          ),
                                        ),
                                        padding: const EdgeInsets.symmetric(
                                          vertical: 6, // Compacted from 10
                                        ),
                                      ),
                                      child: FittedBox(
                                        fit: BoxFit.scaleDown,
                                        child: Text(
                                          "Entrada",
                                          style: GoogleFonts.outfit(
                                            color: statusColor,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                } else {
                                  // Adelantar Mode
                                  // Don't show button if it is too far in future (e.g. > 2 hours?) - Optional
                                  // Keeping logic same as before
                                  return Expanded(
                                    child: ElevatedButton(
                                      onPressed: () =>
                                          _showAdelantoDialog(course),
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: const Color(
                                          0xFFF59E0B,
                                        ), // Amber
                                        foregroundColor: Colors.white,
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(
                                            12,
                                          ),
                                        ),
                                        padding: const EdgeInsets.symmetric(
                                          vertical: 6, // Compacted from 10
                                        ),
                                        elevation: 0,
                                      ),
                                      child: FittedBox(
                                        // Removed const
                                        fit: BoxFit.scaleDown,
                                        child: Text(
                                          "Adelantar Clase",
                                          style: GoogleFonts.outfit(
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                }
                              },
                            ),

                          if (inProgress) ...[
                            if (course.canMarkExit)
                              Expanded(
                                child: ElevatedButton(
                                  onPressed: () => _handleAttendance(
                                    "course_exit",
                                    course.id,
                                  ),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: statusColor,
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    padding: const EdgeInsets.symmetric(
                                      vertical: 6, // Compacted from 10
                                    ),
                                    elevation: 2,
                                  ),
                                  child: FittedBox(
                                    // Prevent wrap
                                    fit: BoxFit.scaleDown,
                                    child: Text(
                                      "Salida",
                                      style: GoogleFonts.outfit(
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                ),
                              )
                            else
                              Expanded(
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 12,
                                  ),
                                  alignment: Alignment.center,
                                  decoration: BoxDecoration(
                                    color: Colors.grey[50],
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: Colors.grey.shade200,
                                    ),
                                  ),
                                  child: Text(
                                    "Salida: ${course.endTime ?? course.exitTimeStr ?? '--:--'}",
                                    style: GoogleFonts.outfit(
                                      color: Colors.grey[500],
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
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
                errorBuilder: (_, _, _) =>
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

  Widget _buildSkeletonLoader(BuildContext context) {
    return SingleChildScrollView(
      physics: const NeverScrollableScrollPhysics(),
      child: Column(
        children: [
          // Header Skeleton
          Container(
            height: 200,
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.only(
                bottomLeft: Radius.circular(36),
                bottomRight: Radius.circular(36),
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      SkeletonWidget.rectangular(height: 16, width: 100),
                      SizedBox(height: 8),
                      SkeletonWidget.rectangular(height: 30, width: 200),
                    ],
                  ),
                ),
                const SkeletonWidget.circular(width: 70, height: 70),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
            child: Column(
              children: const [
                SkeletonWidget.rounded(height: 180), // Status Card
                SizedBox(height: 24),
                SkeletonWidget.rounded(height: 120), // Next Class
                SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(child: SkeletonWidget.rounded(height: 100)),
                    SizedBox(width: 8),
                    Expanded(child: SkeletonWidget.rounded(height: 100)),
                    SizedBox(width: 8),
                    Expanded(child: SkeletonWidget.rounded(height: 100)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
