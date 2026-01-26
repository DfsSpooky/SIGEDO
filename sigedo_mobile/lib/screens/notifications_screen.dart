import 'package:flutter/material.dart';
import 'package:flutter_html/flutter_html.dart';
import 'package:google_fonts/google_fonts.dart';
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

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  Future<void> _loadNotifications() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final data = await _apiService.getNotifications();
      setState(() {
        _notifications = data['notifications'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _markAsRead(int id, int index) async {
    // Optimistic update
    setState(() {
      _notifications[index]['leido'] = true;
    });

    try {
      final success = await _apiService.markNotificationAsRead(id);
      if (!success && mounted) {
        // Revert if failed
        setState(() {
          _notifications[index]['leido'] = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _notifications[index]['leido'] = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6), // Light Grey
      appBar: AppBar(
        title: Text(
          "Avisos",
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold, fontSize: 22),
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF1F2937),
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 0,
        automaticallyImplyLeading:
            false, // Hide back button if in tab bar context, or keep it if pushed
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF4F46E5)),
            onPressed: _loadNotifications,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF4F46E5)),
            )
          : _notifications.isEmpty
          ? _buildEmptyState()
          : ListView.builder(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
              itemCount: _notifications.length,
              itemBuilder: (ctx, index) {
                final notif = _notifications[index];
                return _buildModernNotificationCard(notif, index);
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
              Icons.notifications_off_outlined,
              size: 60,
              color: Color(0xFF4F46E5),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            "Sin novedades",
            style: GoogleFonts.outfit(
              color: const Color(0xFF1F2937),
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            "Te avisaremos cuando haya algo importante.",
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(color: Colors.grey[500], fontSize: 16),
          ),
        ],
      ),
    );
  }

  Widget _buildModernNotificationCard(dynamic notif, int index) {
    final bool read = notif['leido'] ?? false;
    final int id = notif['id'];
    final String dateStr = notif['fecha_creacion'].toString().split('T')[0];
    final String rawMessage = notif['mensaje'] ?? "Sin contenido";

    return Dismissible(
      key: Key(id.toString()),
      direction:
          DismissDirection.none, // Disable swipe for now as we don't delete
      child: GestureDetector(
        onTap: () {
          if (!read) _markAsRead(id, index);
          _showNotificationDetails(rawMessage);
        },
        child: Container(
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: !read
                ? Border.all(
                    color: const Color(0xFF4F46E5).withValues(alpha: 0.3),
                    width: 1.5,
                  )
                : Border.all(color: Colors.transparent),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.04),
                blurRadius: 15,
                offset: const Offset(0, 5),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // --- ICON INDICATOR ---
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: !read
                            ? const Color(0xFF4F46E5)
                            : Colors.grey[100],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        !read
                            ? Icons.mark_email_unread_outlined
                            : Icons.drafts_outlined,
                        color: !read ? Colors.white : Colors.grey[400],
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 16),

                    // --- CONTENT PREVIEW ---
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                !read ? "Nuevo Aviso" : "Aviso Leído",
                                style: GoogleFonts.outfit(
                                  color: !read
                                      ? const Color(0xFF4F46E5)
                                      : Colors.grey[500],
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.5,
                                ),
                              ),
                              Text(
                                dateStr,
                                style: GoogleFonts.outfit(
                                  color: Colors.grey[400],
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),

                          // HTML PREVIEW (Limited height/lines)
                          Html(
                            data: rawMessage,
                            style: {
                              "body": Style(
                                margin: Margins.zero,
                                padding: HtmlPaddings.zero,
                                fontSize: FontSize(15),
                                color: const Color(0xFF374151), // Gray-700
                                fontWeight: !read
                                    ? FontWeight.w600
                                    : FontWeight.normal,
                                maxLines: 2,
                                textOverflow: TextOverflow.ellipsis,
                                fontFamily: GoogleFonts.outfit().fontFamily,
                              ),
                              "strong": Style(
                                fontWeight: FontWeight.bold,
                                color: Colors.indigo,
                              ), // Highlight bold text
                            },
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // --- FOOTER BUTTON (Only if unread, or for details) ---
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: !read
                      ? const Color(0xFF4F46E5).withValues(alpha: 0.05)
                      : Colors.grey[50],
                  borderRadius: const BorderRadius.only(
                    bottomLeft: Radius.circular(20),
                    bottomRight: Radius.circular(20),
                  ),
                ),
                child: Center(
                  child: Text(
                    "Ver Detalles",
                    style: GoogleFonts.outfit(
                      color: !read ? const Color(0xFF4F46E5) : Colors.grey[500],
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showNotificationDetails(String htmlContent) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.4,
        maxChildSize: 0.9,
        builder: (_, controller) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(30)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 12),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 20),

              Text(
                "Detalle del Aviso",
                style: GoogleFonts.outfit(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Divider(height: 30),

              Expanded(
                child: ListView(
                  controller: controller,
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  children: [
                    Html(
                      data: htmlContent,
                      style: {
                        "body": Style(
                          fontSize: FontSize(16),
                          color: const Color(0xFF374151),
                          lineHeight: LineHeight(1.5),
                          fontFamily: GoogleFonts.outfit().fontFamily,
                        ),
                      },
                    ),
                    const SizedBox(height: 40),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => Navigator.pop(ctx),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF4F46E5),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                        child: Text(
                          "Entendido",
                          style: GoogleFonts.outfit(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
