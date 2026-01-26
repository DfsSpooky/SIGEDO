import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final ApiService _apiService = ApiService();

  // State
  CalendarFormat _calendarFormat = CalendarFormat.month;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;

  // Data
  Map<DateTime, List<dynamic>> _events = {};
  List<dynamic> _selectedEvents = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _selectedDay = _focusedDay;
    _fetchHistory(_focusedDay.month, _focusedDay.year);
  }

  Future<void> _fetchHistory(int month, int year) async {
    setState(() => _isLoading = true);
    try {
      final data = await _apiService.getAttendanceHistory(
        month: month,
        year: year,
      );

      final Map<DateTime, List<dynamic>> newEvents = {};

      for (var dayData in data) {
        // Parse date "YYYY-MM-DD"
        final dateStr = dayData['date'];
        final dateParts = dateStr.split('-');
        final date = DateTime.utc(
          int.parse(dateParts[0]),
          int.parse(dateParts[1]),
          int.parse(dateParts[2]),
        );

        // Combine General + Courses
        List<dynamic> dayEvents = [];

        // Add General Gate Event if exists
        if (dayData['general'] != null) {
          dayEvents.add({"type": "GATE", ...dayData['general']});
        }

        // Add Courses
        if (dayData['courses'] != null) {
          for (var c in dayData['courses']) {
            dayEvents.add({"type": "COURSE", ...c});
          }
        }

        newEvents[date] = dayEvents;
      }

      setState(() {
        _events = newEvents;
        _selectedEvents = _getEventsForDay(_selectedDay ?? DateTime.now());
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  List<dynamic> _getEventsForDay(DateTime day) {
    // Normalize date to UTC/Midnight to match key
    final dateKey = DateTime.utc(day.year, day.month, day.day);
    return _events[dateKey] ?? [];
  }

  void _onDaySelected(DateTime selectedDay, DateTime focusedDay) {
    if (!isSameDay(_selectedDay, selectedDay)) {
      setState(() {
        _selectedDay = selectedDay;
        _focusedDay = focusedDay;
        _selectedEvents = _getEventsForDay(selectedDay);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6),
      appBar: AppBar(
        title: Text(
          "Historial de Asistencia",
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF1F2937),
        elevation: 0,
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Calendar
          _buildCalendar(),

          const SizedBox(height: 16),

          // Event List using Expanded
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.only(top: 24, left: 20, right: 20),
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(30),
                  topRight: Radius.circular(30),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 10,
                    offset: Offset(0, -5),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedDay != null
                            ? DateFormat(
                                'EEEE, d MMMM',
                                'es_ES',
                              ).format(_selectedDay!)
                            : 'Selecciona un día', // Needs locale setup in main, default en
                        style: GoogleFonts.outfit(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF1F2937),
                        ),
                      ),
                      if (_isLoading)
                        const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  if (_selectedEvents.isEmpty)
                    _buildEmptyState()
                  else
                    Expanded(
                      child: ListView.builder(
                        itemCount: _selectedEvents.length,
                        physics: const BouncingScrollPhysics(),
                        itemBuilder: (context, index) {
                          return _buildEventCard(_selectedEvents[index]);
                        },
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCalendar() {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: TableCalendar(
        firstDay: DateTime.utc(2024, 1, 1),
        lastDay: DateTime.utc(2030, 12, 31),
        focusedDay: _focusedDay,
        calendarFormat: _calendarFormat,
        selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
        onDaySelected: _onDaySelected,
        onPageChanged: (focusedDay) {
          _focusedDay = focusedDay;
          _fetchHistory(focusedDay.month, focusedDay.year);
        },
        eventLoader: _getEventsForDay,
        startingDayOfWeek: StartingDayOfWeek.monday,

        // Styles
        onFormatChanged: (format) {
          if (_calendarFormat != format) {
            setState(() {
              _calendarFormat = format;
            });
          }
        },
        calendarStyle: CalendarStyle(
          selectedDecoration: const BoxDecoration(
            color: Color(0xFF4F46E5),
            shape: BoxShape.circle,
          ),
          todayDecoration: BoxDecoration(
            color: const Color(0xFF4F46E5).withValues(alpha: 0.3),
            shape: BoxShape.circle,
          ),
          markerDecoration: const BoxDecoration(
            color: Color(0xFF10B981), // Green dot for generic event
            shape: BoxShape.circle,
          ),
        ),
        headerStyle: HeaderStyle(
          titleCentered: true,
          formatButtonVisible: false,
          titleTextStyle: GoogleFonts.outfit(
            fontWeight: FontWeight.bold,
            fontSize: 16,
          ),
        ),

        // Builder for custom markers (colors based on status)
        calendarBuilders: CalendarBuilders(
          markerBuilder: (context, date, events) {
            if (events.isEmpty) return null;

            // Check if any event is Late or Absent
            bool hasIssues = events.any((e) {
              final map = e as Map;
              return map['isLate'] == true || map['status'] == 'ABSENT';
            });

            return Positioned(
              bottom: 1,
              child: Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: hasIssues ? Colors.orange : const Color(0xFF10B981),
                ),
                width: 6.0,
                height: 6.0,
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Expanded(
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.event_available, size: 60, color: Colors.grey[300]),
            const SizedBox(height: 16),
            Text(
              "Sin registros",
              style: GoogleFonts.outfit(color: Colors.grey[500], fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEventCard(dynamic event) {
    bool isGate = event['type'] == 'GATE';
    String title = isGate
        ? "Control General"
        : (event['courseName'] ?? 'Clase');
    String status = event['status'] ?? 'UNKNOWN';
    String entry = event['entryTime'] ?? '--:--';
    String exit = event['exitTime'] ?? '--:--';
    bool isLate = event['isLate'] == true;

    Color color;
    IconData icon;

    if (isGate) {
      color = const Color(0xFF6366F1); // Indigo
      icon = Icons.door_front_door_outlined;
    } else {
      color = const Color(0xFFEC4899); // Pink
      icon = Icons.class_outlined;
    }

    // Status Color Override
    Color statusColor = Colors.grey;
    String statusText = "";

    if (status == 'COMPLETED') {
      statusColor = const Color(0xFF10B981); // Green
      statusText = "Completado";
    } else if (status == 'IN_PROGRESS' || status == 'INCOMPLETE') {
      statusColor = const Color(0xFFF59E0B); // Amber
      statusText = "En Curso/Incompleto";
    } else if (status == 'ABSENT') {
      statusColor = const Color(0xFFEF4444); // Red
      statusText = "Ausente";
    }

    if (isLate) {
      statusText += " • Tarde";
      statusColor = Colors.orange;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.grey.shade100),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.05),
            blurRadius: 5,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // Icon
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 16),

          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.outfit(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: const Color(0xFF1F2937),
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.access_time, size: 12, color: Colors.grey[400]),
                    const SizedBox(width: 4),
                    Text(
                      "$entry - $exit",
                      style: GoogleFonts.outfit(
                        fontSize: 12,
                        color: Colors.grey[600],
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Status Badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              statusText,
              style: GoogleFonts.outfit(
                color: statusColor,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
