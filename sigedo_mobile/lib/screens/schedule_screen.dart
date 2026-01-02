import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/api_service.dart';

class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({super.key});

  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<dynamic>> _scheduleFuture;

  @override
  void initState() {
    super.initState();
    _scheduleFuture = _apiService.getSchedule();
  }

  // Mapa para traducir días numéricos (FullCalendar: Sunday=0 ... Saturday=6)
  // Pero hemos visto que en el backend estamos enviando daysOfWeek=[1] para Lunes.
  String _getDayName(int day) {
    switch (day) {
      case 1:
        return 'Lunes';
      case 2:
        return 'Martes';
      case 3:
        return 'Miércoles';
      case 4:
        return 'Jueves';
      case 5:
        return 'Viernes';
      case 6:
        return 'Sábado';
      case 0:
        return 'Domingo';
      default:
        return '';
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _scheduleFuture = _apiService.getSchedule();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6), // Light Grey
      appBar: AppBar(
        title: Text(
          "Mi Horario",
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold, fontSize: 22),
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF1F2937),
        elevation: 0,
        centerTitle: false,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF4F46E5)),
            onPressed: _refresh,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: FutureBuilder<List<dynamic>>(
        future: _scheduleFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(color: Color(0xFF4F46E5)),
            );
          } else if (snapshot.hasError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  const SizedBox(height: 16),
                  Text(
                    "Error al cargar horario",
                    style: GoogleFonts.outfit(color: Colors.grey[700]),
                  ),
                  TextButton(
                    onPressed: _refresh,
                    child: Text(
                      "Reintentar",
                      style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            );
          } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return _buildEmptyState();
          }

          final events = snapshot.data!;
          // Agrupar por día
          final Map<int, List<dynamic>> eventsByDay = {};

          for (var event in events) {
            if (event.containsKey('daysOfWeek')) {
              List<dynamic> days = event['daysOfWeek'];
              for (var day in days) {
                if (!eventsByDay.containsKey(day)) {
                  eventsByDay[day] = [];
                }
                eventsByDay[day]!.add(event);
              }
            }
          }

          // Ordenar claves de días
          final sortedDays = eventsByDay.keys.toList()..sort();

          if (sortedDays.isEmpty) return _buildEmptyState();

          return ListView.builder(
            padding: const EdgeInsets.all(20.0),
            physics: const BouncingScrollPhysics(),
            itemCount: sortedDays.length,
            itemBuilder: (context, index) {
              final day = sortedDays[index];
              final dayEvents = eventsByDay[day]!;

              // Ordenar eventos del día por hora de inicio
              dayEvents.sort(
                (a, b) => a['startTime'].compareTo(b['startTime']),
              );

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildDayHeader(_getDayName(day)),
                  const SizedBox(height: 12),
                  ...dayEvents.map((event) => _buildClassCard(event)),
                  const SizedBox(height: 24),
                ],
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF4F46E5).withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.calendar_today_outlined,
              size: 60,
              color: Color(0xFF4F46E5),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            "Sin horario asignado",
            style: GoogleFonts.outfit(
              color: const Color(0xFF1F2937),
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            "No tienes clases programadas para este periodo.",
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(color: Colors.grey[500], fontSize: 16),
          ),
        ],
      ),
    );
  }

  Widget _buildDayHeader(String dayName) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0xFF4F46E5),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF4F46E5).withValues(alpha: 0.3),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Text(
            dayName,
            style: GoogleFonts.outfit(
              color: Colors.white,
              fontWeight: FontWeight.bold,
              fontSize: 14,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(child: Container(height: 1, color: Colors.grey[300])),
      ],
    );
  }

  Widget _buildClassCard(dynamic event) {
    final String startTime = event['startTime'].toString().substring(
      0,
      5,
    ); // HH:MM
    final String endTime = event['endTime'].toString().substring(0, 5); // HH:MM
    final String title = event['title'] ?? 'Sin nombre';
    // Nuevos campos del backend
    final String specialties = event['specialties'] ?? '';
    final String classroom = event['classroom'] ?? 'Sin Aula';

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 15,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: IntrinsicHeight(
        child: Row(
          children: [
            // Left Time Strip
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
              decoration: BoxDecoration(
                color: const Color(0xFFEEF2FF), // Very clear indigo
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(20),
                  bottomLeft: Radius.circular(20),
                ),
                border: Border(right: BorderSide(color: Colors.grey.shade200)),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    startTime,
                    style: GoogleFonts.outfit(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFF4F46E5),
                    ),
                  ),
                  Container(
                    width: 2,
                    height: 12,
                    color: Colors.grey[300],
                    margin: const EdgeInsets.symmetric(vertical: 4),
                  ),
                  Text(
                    endTime,
                    style: GoogleFonts.outfit(
                      fontSize: 14,
                      color: Colors.grey[500],
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),

            // Right Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      title,
                      style: GoogleFonts.outfit(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: const Color(0xFF1F2937),
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 8),

                    // Specialties Badge
                    if (specialties.isNotEmpty)
                      Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(
                            0xFFEC4899,
                          ).withValues(alpha: 0.1), // Pink tint
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          specialties,
                          style: GoogleFonts.outfit(
                            color: const Color(0xFFDB2777), // Pink 600
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),

                    // Classroom Row
                    Row(
                      children: [
                        Icon(
                          Icons.meeting_room_outlined,
                          size: 16,
                          color: Colors.grey[500],
                        ),
                        const SizedBox(width: 4),
                        Text(
                          classroom,
                          style: GoogleFonts.outfit(
                            fontSize: 13,
                            color: Colors.grey[600],
                            fontWeight: FontWeight.w500,
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
      ),
    );
  }
}
