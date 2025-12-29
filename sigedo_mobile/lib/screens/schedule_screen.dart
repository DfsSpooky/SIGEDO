import 'package:flutter/material.dart';
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

  // Mapa para traducir días numéricos de FullCalendar (Sunday=0) si aplica,
  // pero el backend devuelve `daysOfWeek`.
  // FullCalendar: 0=Domingo, 1=Lunes...
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<dynamic>>(
        future: _scheduleFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return Center(child: Text("Error: ${snapshot.error}"));
          } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text("No hay horarios asignados."));
          }

          final events = snapshot.data!;
          // Agrupar por día
          final Map<int, List<dynamic>> eventsByDay = {};
          
          for (var event in events) {
            // Check if it's a recurring event with daysOfWeek
            if (event.containsKey('daysOfWeek')) {
                List<dynamic> days = event['daysOfWeek'];
                for (var day in days) {
                    if (!eventsByDay.containsKey(day)) {
                        eventsByDay[day] = [];
                    }
                    eventsByDay[day]!.add(event);
                }
            } 
            // Handle special days (one-time events) if needed, or skip them for general schedule view
            // For now, we focus on weekly schedule, so we skip one-time events unless they fall into a specific day view logic.
            // If the user wants to see holidays, we might need a Calendar View instead of a simple List.
            // But to prevent crash, we just skip parsing if key is missing.
          }

          // Ordenar claves de días (1=Lunes, 2=Martes...)
          final sortedDays = eventsByDay.keys.toList()..sort();

          return ListView.builder(
            padding: const EdgeInsets.all(16.0),
            itemCount: sortedDays.length,
            itemBuilder: (context, index) {
                final day = sortedDays[index];
                final dayEvents = eventsByDay[day]!;
                
                // Ordenar eventos del día por hora de inicio
                dayEvents.sort((a, b) => a['startTime'].compareTo(b['startTime']));

                return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                        Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8.0),
                            child: Text(
                                _getDayName(day),
                                style: const TextStyle(
                                    fontSize: 20, 
                                    fontWeight: FontWeight.bold,
                                    color: Colors.indigo
                                ),
                            ),
                        ),
                        ...dayEvents.map((event) => Card(
                            elevation: 2,
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                                leading: const Icon(Icons.class_, color: Colors.indigo),
                                title: Text(event['title'], style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Text("${event['startTime']} - ${event['endTime']}"),
                            ),
                        )),
                        const SizedBox(height: 10),
                    ],
                );
            },
          );
        },
      ),
    );
  }
}
