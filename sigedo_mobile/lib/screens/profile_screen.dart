import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/theme_provider.dart';

class ProfileScreen extends StatelessWidget { // Changed to Stateless as Provider handles state
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const CircleAvatar(
          radius: 50,
          backgroundColor: Colors.indigo,
          child: Icon(Icons.person, size: 50, color: Colors.white),
        ),
        const SizedBox(height: 16),
        const Center(
          child: Text(
            "Mi Perfil",
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
        ),
        const SizedBox(height: 32),
        const Divider(),
        SwitchListTile(
          title: const Text("Modo Oscuro"),
          subtitle: const Text("Cambiar apariencia de la aplicación"),
          value: themeProvider.isDarkMode,
          onChanged: (val) {
            themeProvider.toggleTheme(val);
          },
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.settings),
          title: const Text("Configuración"),
          onTap: () {},
        ),
        ListTile(
          leading: const Icon(Icons.info),
          title: const Text("Acerca de SIGEDO"),
          subtitle: const Text("Versión 1.0.0"),
          onTap: () {},
        ),
      ],
    );
  }
}
