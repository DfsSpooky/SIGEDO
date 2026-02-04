import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import '../utils/constants.dart';

class ConfigService {
  static Future<Map<String, dynamic>?> getInstitutionConfig() async {
    final url = Uri.parse(
      '${AppConstants.baseUrl}${AppConstants.publicConfigEndpoint}',
    );
    try {
      final response = await http.get(url);

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        if (data['logo'] != null &&
            !data['logo'].toString().startsWith('http')) {
          data['logo'] = '${AppConstants.baseUrl}${data['logo']}';
        }
        return data;
      } else {
        debugPrint('Error fetching config: ${response.statusCode}');
        return null;
      }
    } catch (e) {
      debugPrint('Error fetching config: $e');
      return null;
    }
  }
}
