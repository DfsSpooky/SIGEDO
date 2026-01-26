import 'dart:io';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:path_provider/path_provider.dart' as path_provider;

class ImageUtils {
  /// Compresses an image file to valid JPEG format.
  ///
  /// - [file]: The original file.
  /// - [quality]: Compression quality (0-100). Default is 85.
  /// - [minWidth]: Target width. Default 1024.
  /// - [minHeight]: Target height. Default 1024.
  static Future<File?> compressImage(
    File file, {
    int quality = 85,
    int minWidth = 1024,
    int minHeight = 1024,
  }) async {
    final dir = await path_provider.getTemporaryDirectory();
    final targetPath =
        '${dir.absolute.path}/temp_${DateTime.now().millisecondsSinceEpoch}.jpg';

    // Compress
    final result = await FlutterImageCompress.compressAndGetFile(
      file.absolute.path,
      targetPath,
      minWidth: minWidth,
      minHeight: minHeight,
      quality: quality,
      format: CompressFormat.jpeg,
    );

    return result != null ? File(result.path) : null;
  }
}
