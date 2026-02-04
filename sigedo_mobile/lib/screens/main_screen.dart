import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/api_service.dart';

import 'dashboard_screen.dart';
import 'notifications_screen.dart';
import 'profile_screen.dart';
import 'schedule_screen.dart';
import 'director_attendance_screen.dart';
import 'credential_screen.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final ApiService _apiService = ApiService();
  int _unreadCount = 0;
  int _selectedIndex = 0;
  bool _isStaff = false;

  @override
  void initState() {
    super.initState();
    _checkNotifications();
    _checkPermissions();
  }

  Future<void> _checkPermissions() async {
    try {
      final teacherData = await _apiService.getTeacherStatus();
      if (mounted) {
        setState(() {
          _isStaff = teacherData.teacher.isStaff;
        });
      }
    } catch (e) {
      debugPrint("Error checking permissions: $e");
    }
  }

  Future<void> _checkNotifications() async {
    try {
      final data = await _apiService.getNotifications();
      if (mounted) {
        setState(() {
          _unreadCount = data['unread_count'] ?? 0;
        });
      }
    } catch (e) {
      debugPrint("Error checking notifications: $e");
    }
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });

    // If user Taps on Notifications (index 2), refresh count when leaving or entering?
    // Optionally refresh notifications when tapping the tab
    if (index == 2) {
      _checkNotifications();
    }
  }

  @override
  Widget build(BuildContext context) {
    List<Widget> screens = [
      const DashboardScreen(),
      const ScheduleScreen(),
      const CredentialScreen(),
      if (_isStaff) const DirectorAttendanceScreen(),
      const NotificationsScreen(),
      const ProfileScreen(),
    ];

    List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(
        icon: Icon(Icons.dashboard_outlined),
        activeIcon: Icon(Icons.dashboard_rounded),
        label: 'Inicio',
      ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.calendar_month_outlined),
        activeIcon: Icon(Icons.calendar_month_rounded),
        label: 'Horario',
      ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.qr_code_outlined),
        activeIcon: Icon(Icons.qr_code_rounded),
        label: 'Carnet',
      ),
      if (_isStaff)
        const BottomNavigationBarItem(
          icon: Icon(Icons.remove_red_eye_outlined),
          activeIcon: Icon(Icons.remove_red_eye_rounded),
          label: 'Monitoreo',
        ),
      BottomNavigationBarItem(
        icon: Badge(
          isLabelVisible: _unreadCount > 0,
          label: Text('$_unreadCount'),
          backgroundColor: Colors.redAccent,
          child: const Icon(Icons.notifications_outlined),
        ),
        activeIcon: Badge(
          isLabelVisible: _unreadCount > 0,
          label: Text('$_unreadCount'),
          backgroundColor: Colors.redAccent,
          child: const Icon(Icons.notifications_rounded),
        ),
        label: 'Avisos',
      ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.person_outline),
        activeIcon: Icon(Icons.person_rounded),
        label: 'Perfil',
      ),
    ];

    // Safety check for index out of bounds if permissions change or reload
    if (_selectedIndex >= screens.length) {
      _selectedIndex = 0;
    }

    return Scaffold(
      // No AppBar anymore
      // Use IndexedStack to preserve state
      body: IndexedStack(
        // Use IndexedStack to preserve state
        index: _selectedIndex,
        children: screens,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 20,
              offset: const Offset(0, -5),
            ),
          ],
        ),
        child: BottomNavigationBar(
          backgroundColor: Colors.white,
          elevation: 0,
          type: BottomNavigationBarType.fixed,
          selectedItemColor: const Color(0xFF4F46E5),
          unselectedItemColor: Colors.grey[400],
          selectedLabelStyle: GoogleFonts.outfit(
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
          unselectedLabelStyle: GoogleFonts.outfit(fontSize: 12),
          items: navItems,
          currentIndex: _selectedIndex,
          onTap: _onItemTapped,
        ),
      ),
    );
  }
}
