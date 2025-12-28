import 'package:flutter/material.dart';
import '../services/api_service.dart';
// import 'package:url_launcher/url_launcher.dart'; // Si quieres abrir URLs

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ApiService _apiService = ApiService();
  late Future<Map<String, dynamic>> _notificationsFuture;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  void _loadNotifications() {
    setState(() {
      _notificationsFuture = _apiService.getNotifications();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Notificaciones"),
        backgroundColor: Colors.indigo,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _notificationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return Center(child: Text("Error: ${snapshot.error}"));
          } else if (!snapshot.hasData) {
            return const Center(child: Text("Sin información."));
          }

          final data = snapshot.data!;
          final List<dynamic> notifications = data['notifications'] ?? [];

          if (notifications.isEmpty) {
            return const Center(child: Text("No tienes notificaciones recientes."));
          }

          return ListView.builder(
            itemCount: notifications.length,
            itemBuilder: (ctx, index) {
              final notif = notifications[index];
              return Card(
                color: notif['leido'] ? Colors.white : Colors.indigo.shade50,
                margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                child: ListTile(
                  leading: Icon(
                    notif['leido'] ? Icons.notifications_none : Icons.notifications_active,
                    color: notif['leido'] ? Colors.grey : Colors.red,
                  ),
                  title: Text(
                    notif['mensaje'],
                    style: TextStyle(
                      fontWeight: notif['leido'] ? FontWeight.normal : FontWeight.bold,
                    ),
                  ),
                  subtitle: Text(notif['fecha_creacion'].toString().split('T')[0]),
                  // Aquí se podría agregar onTap para marcar como leída
                ),
              );
            },
          );
        },
      ),
    );
  }
}
