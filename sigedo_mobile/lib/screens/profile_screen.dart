import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart'; // Import Google Fonts
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import 'login_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  void _handleLogout(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          "Cerrar Sesión",
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
        ),
        content: Text(
          "¿Estás seguro que deseas salir de la aplicación?",
          style: GoogleFonts.outfit(),
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(
              "Cancelar",
              style: GoogleFonts.outfit(color: Colors.grey),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(ctx).pop(); // Cerrar diálogo

              final authProvider = Provider.of<AuthProvider>(
                context,
                listen: false,
              );
              await authProvider.logout();

              if (context.mounted) {
                // Navegar al login y eliminar historial
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (context) => const LoginScreen()),
                  (route) => false,
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.redAccent,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: Text(
              "Cerrar Sesión",
              style: GoogleFonts.outfit(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);
    final authProvider = Provider.of<AuthProvider>(context);
    final teacher = authProvider.teacherData?.teacher;

    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6), // Light Grey Background
      body: SingleChildScrollView(
        child: Column(
          children: [
            // --- HEADER WITH GRADIENT ---
            Stack(
              alignment: Alignment.center,
              clipBehavior: Clip.none,
              children: [
                // Gradient Background
                Container(
                  height: 350,
                  width: double.infinity,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Color(0xFF4F46E5),
                        Color(0xFF7C3AED),
                      ], // Indigo to Purple
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.only(
                      bottomLeft: Radius.circular(40),
                      bottomRight: Radius.circular(40),
                    ),
                  ),
                ),

                // Content inside Header
                Positioned(
                  top: 60,
                  child: Column(
                    children: [
                      // Avatar
                      Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.5),
                            width: 1,
                          ),
                        ),
                        child: CircleAvatar(
                          radius: 60,
                          backgroundColor: Colors.white,
                          backgroundImage: teacher?.photoUrl != null
                              ? NetworkImage(teacher!.photoUrl!)
                              : null,
                          child: teacher?.photoUrl == null
                              ? Text(
                                  teacher?.name.substring(0, 1).toUpperCase() ??
                                      "U",
                                  style: GoogleFonts.outfit(
                                    fontSize: 40,
                                    fontWeight: FontWeight.bold,
                                    color: const Color(0xFF4F46E5),
                                  ),
                                )
                              : null,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        teacher?.name ?? "Usuario Invitado",
                        style: GoogleFonts.outfit(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        teacher?.email ?? "Sin correo registrado",
                        style: GoogleFonts.outfit(
                          color: Colors.white70,
                          fontSize: 14,
                        ),
                      ),
                      if (teacher?.dni != null)
                        Container(
                          margin: const EdgeInsets.only(top: 8),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            "DNI: ${teacher!.dni}",
                            style: GoogleFonts.outfit(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(
              height: 40,
            ), // Spacer for overlapping content if needed
            // --- SETTINGS LIST ---
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSectionTitle("Preferencias"),
                  const SizedBox(height: 10),
                  _buildSettingsTile(
                    icon: Icons.dark_mode_outlined,
                    iconColor: Colors.purple,
                    title: "Modo Oscuro",
                    subtitle: "Cambiar apariencia de la app",
                    trailing: Switch(
                      value: themeProvider.isDarkMode,
                      activeThumbColor: const Color(0xFF4F46E5),
                      onChanged: (val) => themeProvider.toggleTheme(val),
                    ),
                  ),

                  const SizedBox(height: 30),
                  _buildSectionTitle("Cuenta"),
                  const SizedBox(height: 10),
                  _buildSettingsTile(
                    icon: Icons.info_outline,
                    iconColor: Colors.blue,
                    title: "Acerca de SIGEDO",
                    subtitle: "v1.0.0",
                    onTap: () {
                      showAboutDialog(
                        context: context,
                        applicationName: "SIGEDO Mobile",
                        applicationVersion: "1.0.0",
                        applicationLegalese: "© 2025 SIGEDO Inc.",
                        children: [
                          const Text(
                            "Sistema de Gestión Docente para control de asistencia y trámites.",
                          ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 10),
                  _buildSettingsTile(
                    icon: Icons.logout_rounded,
                    iconColor: Colors.redAccent,
                    title: "Cerrar Sesión",
                    titleColor: Colors.redAccent,
                    onTap: () => _handleLogout(context),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: GoogleFonts.outfit(
        color: Colors.grey[600],
        fontSize: 14,
        fontWeight: FontWeight.bold,
        letterSpacing: 1,
      ),
    );
  }

  Widget _buildSettingsTile({
    required IconData icon,
    required Color iconColor,
    required String title,
    String? subtitle,
    Widget? trailing,
    VoidCallback? onTap,
    Color? titleColor,
  }) {
    return Container(
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
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        leading: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: iconColor, size: 24),
        ),
        title: Text(
          title,
          style: GoogleFonts.outfit(
            fontWeight: FontWeight.w600,
            fontSize: 16,
            color: titleColor ?? const Color(0xFF1F2937),
          ),
        ),
        subtitle: subtitle != null
            ? Text(
                subtitle,
                style: GoogleFonts.outfit(
                  color: Colors.grey[400],
                  fontSize: 13,
                ),
              )
            : null,
        trailing:
            trailing ?? const Icon(Icons.chevron_right, color: Colors.grey),
      ),
    );
  }
}
