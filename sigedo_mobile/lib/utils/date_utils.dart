class DateUtilsLima {
  // Peru is UTC-5
  static DateTime get now {
    return DateTime.now().toUtc().subtract(const Duration(hours: 5));
  }

  static String formatTime(DateTime dt) {
    return "${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}";
  }

  static DateTime? parseTimeString(String? timeStr) {
    if (timeStr == null || timeStr.isEmpty) return null;
    try {
      final parts = timeStr.split(':');
      final h = int.parse(parts[0]);
      final m = int.parse(parts[1]);
      final today = now;
      // Return as UTC to match 'now' behavior
      return DateTime.utc(today.year, today.month, today.day, h, m);
    } catch (e) {
      return null;
    }
  }
}
