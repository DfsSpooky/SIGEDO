import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import '../utils/constants.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  StreamController<dynamic>? _streamController;
  bool _isConnected = false;

  // Singleton pattern
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  bool get isConnected => _isConnected;
  Stream<dynamic>? get stream => _streamController?.stream;

  Future<void> connect(String token) async {
    if (_isConnected) return;

    try {
      // Replace http/https with ws/wss
      String wsUrl = AppConstants.baseUrl.replaceFirst('http', 'ws');
      wsUrl = '$wsUrl/ws/notifications/?token=$token';

      debugPrint("Connecting to WebSocket: $wsUrl");

      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _streamController = StreamController<dynamic>.broadcast();

      _channel!.stream.listen(
        (message) {
          debugPrint("WS Message: $message");
          _streamController?.add(jsonDecode(message));
        },
        onDone: () {
          debugPrint("WebSocket Closed");
          _isConnected = false;
          _reconnect(token);
        },
        onError: (error) {
          debugPrint("WebSocket Error: $error");
          _isConnected = false;
          _reconnect(token);
        },
      );

      _isConnected = true;
    } catch (e) {
      debugPrint("WebSocket Connection Failed: $e");
      _isConnected = false;
      // Use retry logic if needed
    }
  }

  void _reconnect(String token) {
    Future.delayed(const Duration(seconds: 5), () {
      if (!_isConnected) {
        debugPrint("Attempting Reconnect...");
        connect(token);
      }
    });
  }

  void disconnect() {
    if (_channel != null) {
      _channel!.sink.close(status.goingAway);
      _isConnected = false;
    }
    _streamController?.close();
  }
}
