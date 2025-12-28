class TeacherData {
  final TeacherInfo teacher;
  final DailyAttendance dailyAttendance;
  final List<CourseAttendance> courses;

  TeacherData({
    required this.teacher,
    required this.dailyAttendance,
    required this.courses,
  });

  factory TeacherData.fromJson(Map<String, dynamic> json) {
    return TeacherData(
      teacher: TeacherInfo.fromJson(json['teacher']),
      dailyAttendance: DailyAttendance.fromJson(json['dailyAttendance']),
      courses: (json['courses'] as List)
          .map((i) => CourseAttendance.fromJson(i))
          .toList(),
    );
  }
}

class TeacherInfo {
  final String name;
  final String dni;
  final String? photoUrl;

  TeacherInfo({required this.name, required this.dni, this.photoUrl});

  factory TeacherInfo.fromJson(Map<String, dynamic> json) {
    return TeacherInfo(
      name: json['name'],
      dni: json['dni'],
      photoUrl: json['photoUrl'],
    );
  }
}

class DailyAttendance {
  final bool entryMarked;
  final bool exitMarked;
  final String? entryTime;
  final String? exitTime;

  DailyAttendance({
    required this.entryMarked,
    required this.exitMarked,
    this.entryTime,
    this.exitTime,
  });

  factory DailyAttendance.fromJson(Map<String, dynamic> json) {
    return DailyAttendance(
      entryMarked: json['entryMarked'] ?? false,
      exitMarked: json['exitMarked'] ?? false,
      entryTime: json['entryTime'],
      exitTime: json['exitTime'],
    );
  }
}

class CourseAttendance {
  final int id;
  final String name;
  final bool entryMarked;
  final bool exitMarked;
  final bool canMarkExit;
  final String? exitTimeStr;

  CourseAttendance({
    required this.id,
    required this.name,
    required this.entryMarked,
    required this.exitMarked,
    required this.canMarkExit,
    this.exitTimeStr,
  });

  factory CourseAttendance.fromJson(Map<String, dynamic> json) {
    return CourseAttendance(
      id: json['id'],
      name: json['name'],
      entryMarked: json['entryMarked'] ?? false,
      exitMarked: json['exitMarked'] ?? false,
      canMarkExit: json['canMarkExit'] ?? false,
      exitTimeStr: json['hora_salida_permitida_str'],
    );
  }
}
