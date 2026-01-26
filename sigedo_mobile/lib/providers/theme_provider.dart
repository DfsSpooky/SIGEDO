import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeProvider with ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.light;

  ThemeMode get themeMode => _themeMode;

  bool get isDarkMode => false; // Always false

  ThemeProvider() {
    _loadTheme();
  }

  void toggleTheme(bool isOn) {
    // Disabled
    // _themeMode = isOn ? ThemeMode.dark : ThemeMode.light;
    // _saveTheme(isOn);
    // notifyListeners();
  }

  Future<void> _loadTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final isDark = prefs.getBool('isDarkMode');
    if (isDark != null) {
      _themeMode = isDark ? ThemeMode.dark : ThemeMode.light;
      notifyListeners();
    }
  }

  // _saveTheme removed
}
