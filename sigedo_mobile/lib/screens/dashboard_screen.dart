import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../models/teacher_data.dart';
import '../services/api_service.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:convert';
import 'dart:io';
import '../services/location_service.dart';
import 'justification_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();

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
          const SnackBar(content: Text('Se requiere permiso de cámara para marcar asistencia.')),
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

    // 3. (Base64 no necesario si usamos AuthProvider que espera File) 
    
    // 4. Enviar al API
    if (mounted) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => const Center(child: CircularProgressIndicator()),
      );

      try {
        // --- NUEVO: Obtener Geolocalización ---
        final locationService = LocationService();
        final position = await locationService.getCurrentLocation();
        // -------------------------------------

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
          scaffoldMessenger.showSnackBar(
             const SnackBar(content: Text('Acción realizada correctamente'), backgroundColor: Colors.green),
          );

          // Recargar datos (Nombre corregido: loadDashboard)
          Provider.of<AuthProvider>(context, listen: false).loadDashboard();
        }
      } catch (e) {
        if (mounted) {
          Navigator.pop(context);
          scaffoldMessenger.showSnackBar(
            SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
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
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: () => auth.loadDashboard(), // Corregido loadDashboardData -> loadDashboard
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // Header de Bienvenida
          Text(
            "$_greeting,",
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
              color: Colors.grey[600],
              fontWeight: FontWeight.normal,
            ),
          ),
          Text(
             teacherInfo?.name ?? "Docente",
            style: Theme.of(context).textTheme.displaySmall,
          ),
          const SizedBox(height: 24),

          // Tarjeta de Asistencia General (Estado del Día)
          _buildDailyAttendanceCard(context, dailyAttendance),
          
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              icon: const Icon(Icons.assignment_late_outlined, size: 18),
              label: const Text("Solicitar Justificación"),
              onPressed: () {
                Navigator.push(context, MaterialPageRoute(builder: (_) => const JustificationScreen()));
              },
              style: TextButton.styleFrom(foregroundColor: Colors.grey[700]),
            ),
          ),

          const SizedBox(height: 12),
          Text(
            "Cursos de Hoy",
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 12),

          if (courses.isEmpty)
             _buildEmptyState(context, "No tienes cursos programados para hoy.\n¡Disfruta tu día!"),

          ...courses.map((course) => _buildCourseCard(context, course)),
          const SizedBox(height: 80), // Espacio final
        ],
      ),
    );
  }

  Widget _buildDailyAttendanceCard(BuildContext context, DailyAttendance? daily) {
    bool isEntryMarked = daily?.entryMarked ?? false;
    bool isExitMarked = daily?.exitMarked ?? false;

    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            colors: isEntryMarked 
                ? [const Color(0xFF1A237E), const Color(0xFF3949AB)] // Azul si marcó
                : [const Color(0xFF00BFA5), const Color(0xFF00897B)], // Verde si falta
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  "Asistencia General",
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
                Icon(
                  isEntryMarked ? Icons.check_circle : Icons.access_time_filled,
                  color: Colors.white.withOpacity(0.8),
                )
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildTimeColumn("Entrada", daily?.entryTime, isEntryMarked),
                Container(width: 1, height: 40, color: Colors.white24),
                _buildTimeColumn("Salida", daily?.exitTime, isExitMarked),
              ],
            ),
            const SizedBox(height: 20),
            
            // Botones de Acción Diaria
            if (!isEntryMarked) 
              _buildActionButton(
                label: "MARCAR ENTRADA", 
                icon: Icons.login,
                color: Colors.white,
                textColor: const Color(0xFF00BFA5),
                onTap: () => _handleAttendance("general_entry", null),
              )
            else if (!isExitMarked)
               _buildActionButton(
                label: "MARCAR SALIDA", 
                icon: Icons.logout,
                color: Colors.white.withOpacity(0.2), // Traslúcido
                textColor: Colors.white,
                onTap: () => _handleAttendance("general_exit", null),
              )
            else
               const Center(child: Text("Jornada Completada ✅", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeColumn(String label, String? time, bool marked) {
    return Column(
      children: [
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        const SizedBox(height: 4),
        Text(
          marked ? (time ?? "--:--") : "--:--",
          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }

  Widget _buildCourseCard(BuildContext context, CourseAttendance course) {
    bool inProgress = course.entryMarked && !course.exitMarked;
    bool completed = course.entryMarked && course.exitMarked;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: inProgress ? Colors.green.shade50 : (completed ? Colors.grey.shade100 : Colors.indigo.shade50),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    Icons.class_, 
                    color: inProgress ? Colors.green : (completed ? Colors.grey : Theme.of(context).primaryColor)
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(course.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      if (inProgress) 
                         const Text("En curso...", style: TextStyle(color: Colors.green, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                if (!course.entryMarked)
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _handleAttendance("course_entry", course.id),
                      icon: const Icon(Icons.login),
                      label: const Text("Entrada"),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Theme.of(context).primaryColor,
                        side: BorderSide(color: Theme.of(context).primaryColor),
                      ),
                    ),
                  ),
                
                if (inProgress) ...[
                   if (course.canMarkExit)
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () => _handleAttendance("course_exit", course.id),
                        icon: const Icon(Icons.logout),
                        label: const Text("Salida"),
                        style: ElevatedButton.styleFrom(backgroundColor: Theme.of(context).primaryColor),
                      ),
                    )
                   else
                    Expanded(
                      child: Container(
                         padding: const EdgeInsets.symmetric(vertical: 12),
                         alignment: Alignment.center,
                         decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(8)),
                         child: Text("Salida a las ${course.exitTimeStr ?? '--:--'}", style: const TextStyle(color: Colors.grey)),
                      ),
                    )
                ],

                if (completed)
                   Expanded(
                     child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        alignment: Alignment.center,
                        child: const Text("Clase Finalizada", style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold)),
                     ),
                   ),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton({
      required String label, 
      required IconData icon, 
      required VoidCallback onTap,
      required Color color,
      required Color textColor,
  }) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        icon: Icon(icon, color: textColor),
        label: Text(label, style: TextStyle(color: textColor, fontWeight: FontWeight.bold)),
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          padding: const EdgeInsets.symmetric(vertical: 12),
          elevation: 0,
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
            Icon(Icons.event_busy, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[500], fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }
}
