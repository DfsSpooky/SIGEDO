import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/theme_provider.dart'; // Import ThemeProvider
import 'screens/splash_screen.dart';

import 'theme/app_theme.dart';

import 'package:firebase_core/firebase_core.dart';
import 'services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await NotificationService().initialize();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()), // Register ThemeProvider
      ],
      child: Consumer<ThemeProvider>( // Listen to theme changes
        builder: (context, themeProvider, child) {
          return MaterialApp(
            title: 'SIGEDO Mobile',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
            darkTheme: AppTheme.darkTheme,
            themeMode: themeProvider.themeMode, // Use dynamic theme mode
            home: const SplashScreen(),
          );
        },
      ),
    );
  }
}


