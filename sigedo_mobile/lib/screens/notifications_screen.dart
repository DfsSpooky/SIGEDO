import 'package:flutter/material.dart';
import '../services/api_service.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _notifications = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  Future<void> _loadNotifications() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await _apiService.getNotifications();
      setState(() {
        _notifications = data['notifications'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _markAsRead(int id, int index) async {
    // Optimistic update
    setState(() {
      _notifications[index]['leido'] = true;
    });

    final success = await _apiService.markNotificationAsRead(id);
    if (!success) {
      // Revert if failed
      if (mounted) {
        setState(() {
           _notifications[index]['leido'] = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Error al marcar como leída")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: const Text("Notificaciones", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black87,
        elevation: 0,
        centerTitle: true,
      ),
      body: _isLoading 
        ? const Center(child: CircularProgressIndicator()) 
        : RefreshIndicator(
            onRefresh: _loadNotifications,
            child: _notifications.isEmpty 
              ? _buildEmptyState()
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  itemCount: _notifications.length,
                  itemBuilder: (ctx, index) {
                    final notif = _notifications[index];
                    return _buildNotificationCard(notif, index);
                  },
                ),
          ),
    );
  }

  Widget _buildEmptyState() {
     return ListView( // To allow pull-to-refresh even on empty
       children: [
         SizedBox(height: MediaQuery.of(context).size.height * 0.3),
         const Center(
           child: Column(
             mainAxisAlignment: MainAxisAlignment.center,
             children: [
               Icon(Icons.notifications_none_outlined, size: 80, color: Colors.grey),
               SizedBox(height: 20),
               Text("No tienes notificaciones", style: TextStyle(color: Colors.grey, fontSize: 18)),
             ],
           ),
         ),
       ],
     );
  }

  Widget _buildNotificationCard(dynamic notif, int index) {
    final bool read = notif['leido'] ?? false;
    final int id = notif['id'];
    final String dateStr = notif['fecha_creacion'].toString().split('T')[0];

    return Dismissible(
      key: Key(id.toString()),
      background: Container(color: Colors.red),
      direction: DismissDirection.endToStart,
      confirmDismiss: (dir) async {
         // Maybe delete functionality later? For now just confirm nothing happens on swipe
         return false; 
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: read ? Colors.white : Colors.indigo.shade50,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 10,
              offset: const Offset(0, 4)
            )
          ],
          border: read ? Border.all(color: Colors.grey.shade200) : Border.all(color: Colors.indigo.shade100, width: 1.5)
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () {
              // 1. Marcar como leída si no lo está
              if (!read) {
                _markAsRead(id, index);
              }
              // 2. Mostrar diálogo con el contenido completo
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text("Detalle de Notificación"),
                  content: SingleChildScrollView(
                    child: Text(notif['mensaje'] ?? "Sin contenido"),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text("Cerrar"),
                    )
                  ],
                ),
              );
            },
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: read ? Colors.grey.shade100 : Colors.white,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      read ? Icons.notifications_none : Icons.notifications_active,
                      color: read ? Colors.grey : Colors.indigo,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          notif['mensaje'] ?? "Sin mensaje",
                          style: TextStyle(
                            fontWeight: read ? FontWeight.normal : FontWeight.bold,
                            fontSize: 14,
                            color: read ? Colors.grey.shade800 : Colors.black87
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          dateStr,
                          style: TextStyle(color: Colors.grey.shade500, fontSize: 12),
                        )
                      ],
                    ),
                  ),
                  if (!read)
                    Container(
                      margin: const EdgeInsets.only(left: 8),
                      width: 10, height: 10,
                      decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                    )
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
