import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

class ConfigService {
  static Future<Map<String, dynamic>?> getInstitutionConfig() async {
    final url = Uri.parse('${AppConstants.baseUrl}/mobile/public-config/');
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
        print('Error fetching config: ${response.statusCode}');
        return null;
      }
    } catch (e) {
      print('Error fetching config: $e');
      return null;
    }
  }
}
