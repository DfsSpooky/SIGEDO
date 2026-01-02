import 'announcement.dart';

class TeacherData {
  final TeacherInfo teacher;
  final DailyAttendance dailyAttendance;
  final List<CourseAttendance> courses;
  final List<Announcement> announcements;
  final AttendanceConfig? attendanceConfig;

  TeacherData({
    required this.teacher,
    required this.dailyAttendance,
    required this.courses,
    this.announcements = const [],
    this.attendanceConfig,
  });

  TeacherData copyWith({
    TeacherInfo? teacher,
    DailyAttendance? dailyAttendance,
    List<CourseAttendance>? courses,
    List<Announcement>? announcements,
    AttendanceConfig? attendanceConfig,
  }) {
    return TeacherData(
      teacher: teacher ?? this.teacher,
      dailyAttendance: dailyAttendance ?? this.dailyAttendance,
      courses: courses ?? this.courses,
      announcements: announcements ?? this.announcements,
      attendanceConfig: attendanceConfig ?? this.attendanceConfig,
    );
  }

  factory TeacherData.fromJson(Map<String, dynamic> json) {
    return TeacherData(
      teacher: TeacherInfo.fromJson(json['teacher'] ?? <String, dynamic>{}),
      dailyAttendance: DailyAttendance.fromJson(
        json['dailyAttendance'] ?? <String, dynamic>{},
      ),
      courses:
          (json['courses'] as List?)
              ?.map((i) => CourseAttendance.fromJson(i))
              .toList() ??
          [],
      announcements:
          (json['announcements'] as List?)
              ?.map((i) => Announcement.fromJson(i))
              .toList() ??
          [],
      attendanceConfig: json['attendanceConfig'] != null
          ? AttendanceConfig.fromJson(json['attendanceConfig'])
          : null,
    );
  }
}

class TeacherInfo {
  final String name;
  final String dni;
  final String? photoUrl;
  final String? email; // NEW
  final String? idQr; // NEW
  final bool isStaff; // NEW

  // Getters for compatibility with CredentialScreen
  String? get foto => photoUrl;

  TeacherInfo({
    required this.name,
    required this.dni,
    this.photoUrl,
    this.email,
    this.idQr,
    this.isStaff = false,
  });

  factory TeacherInfo.fromJson(Map<String, dynamic> json) {
    return TeacherInfo(
      name: json['name'],
      dni: json['dni'],
      photoUrl: json['photoUrl'] ?? json['foto'], // Flexible key
      email: json['email'],
      idQr: json['id_qr'] ?? json['rfid_uid'], // Map backend field
      isStaff: json['is_staff'] ?? false,
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

  DailyAttendance copyWith({
    bool? entryMarked,
    bool? exitMarked,
    String? entryTime,
    String? exitTime,
  }) {
    return DailyAttendance(
      entryMarked: entryMarked ?? this.entryMarked,
      exitMarked: exitMarked ?? this.exitMarked,
      entryTime: entryTime ?? this.entryTime,
      exitTime: exitTime ?? this.exitTime,
    );
  }

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
  final String? startTime;
  final String? endTime;
  final String? classroom;

  CourseAttendance({
    required this.id,
    required this.name,
    required this.entryMarked,
    required this.exitMarked,
    required this.canMarkExit,
    this.exitTimeStr,
    this.startTime,
    this.endTime,
    this.classroom,
  });

  CourseAttendance copyWith({
    int? id,
    String? name,
    bool? entryMarked,
    bool? exitMarked,
    bool? canMarkExit,
    String? exitTimeStr,
    String? startTime,
    String? endTime,
    String? classroom,
  }) {
    return CourseAttendance(
      id: id ?? this.id,
      name: name ?? this.name,
      entryMarked: entryMarked ?? this.entryMarked,
      exitMarked: exitMarked ?? this.exitMarked,
      canMarkExit: canMarkExit ?? this.canMarkExit,
      exitTimeStr: exitTimeStr ?? this.exitTimeStr,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      classroom: classroom ?? this.classroom,
    );
  }

  factory CourseAttendance.fromJson(Map<String, dynamic> json) {
    return CourseAttendance(
      id: json['id'],
      name: json['name'],
      entryMarked: json['entryMarked'] ?? false,
      exitMarked: json['exitMarked'] ?? false,
      canMarkExit: json['canMarkExit'] ?? false,
      exitTimeStr: json['hora_salida_permitida_str'],
      startTime: json['startTime'],
      endTime: json['endTime'],
      classroom: json['classroom'],
    );
  }
}

class AttendanceConfig {
  final String? generalEntryStartTime;
  final String? generalEntryEndTime;

  AttendanceConfig({this.generalEntryStartTime, this.generalEntryEndTime});

  factory AttendanceConfig.fromJson(Map<String, dynamic> json) {
    return AttendanceConfig(
      generalEntryStartTime: json['generalEntryStartTime'],
      generalEntryEndTime: json['generalEntryEndTime'],
    );
  }
}
