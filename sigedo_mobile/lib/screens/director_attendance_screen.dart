import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/api_service.dart';
import 'analytics_screen.dart';

class DirectorAttendanceScreen extends StatefulWidget {
  const DirectorAttendanceScreen({super.key});

  @override
  State<DirectorAttendanceScreen> createState() =>
      _DirectorAttendanceScreenState();
}

class _DirectorAttendanceScreenState extends State<DirectorAttendanceScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _events = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadFeed();
  }

  Future<void> _loadFeed() async {
    setState(() => _isLoading = true);
    final events = await _apiService.getDirectorAttendanceFeed();
    if (mounted) {
      setState(() {
        _events = events;
        _isLoading = false;
      });
    }
  }

  Future<void> _refresh() async {
    await _loadFeed();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Monitoreo en Vivo',
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        actions: [
          IconButton(
            icon: const Icon(Icons.bar_chart_rounded),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const DirectorAnalyticsScreen(),
                ),
              );
            },
          ),
        ],
      ),
      backgroundColor: Colors.grey[50],
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: _events.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.3,
                        ),
                        Center(
                          child: Text(
                            "No hay registros de asistencia hoy.",
                            style: GoogleFonts.outfit(color: Colors.grey),
                          ),
                        ),
                      ],
                    )
                  : ListView.builder(
                      itemCount: _events.length,
                      padding: const EdgeInsets.all(16),
                      itemBuilder: (context, index) {
                        final event = _events[index];
                        return _buildEventCard(event);
                      },
                    ),
            ),
    );
  }

  Widget _buildEventCard(Map<String, dynamic> event) {
    final bool isLate = event['isLate'] == true;
    final String time = event['entryTime'] ?? '--:--';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          children: [
            // Avatar
            CircleAvatar(
              radius: 24,
              backgroundColor: Colors.indigo[50],
              backgroundImage: event['teacherPhoto'] != null
                  ? NetworkImage(event['teacherPhoto'])
                  : null,
              child: event['teacherPhoto'] == null
                  ? Text(
                      (event['teacherName'] as String?)?.characters.first
                              .toUpperCase() ??
                          "?",
                      style: GoogleFonts.outfit(
                        color: Colors.indigo,
                        fontWeight: FontWeight.bold,
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 16),
            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    event['teacherName'] ?? "Desconocido",
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    event['courseName'] ?? "",
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w600,
                      color: Colors.grey[800],
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    event['specialty'] ?? "",
                    style: GoogleFonts.outfit(
                      color: Colors.grey[600],
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            // Time Badge
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: isLate ? Colors.orange[50] : Colors.green[50],
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isLate
                          ? Colors.orange.withValues(alpha: 0.3)
                          : Colors.green.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Text(
                    time,
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.bold,
                      color: isLate ? Colors.orange[800] : Colors.green[800],
                      fontSize: 14,
                    ),
                  ),
                ),
                if (event['exitTime'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4.0),
                    child: Text(
                      "Salida: ${event['exitTime']}",
                      style: GoogleFonts.outfit(
                        fontSize: 10,
                        color: Colors.grey,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
