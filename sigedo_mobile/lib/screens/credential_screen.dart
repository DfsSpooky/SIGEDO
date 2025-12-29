import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../providers/auth_provider.dart';

class CredentialScreen extends StatelessWidget {
  const CredentialScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthProvider>(context);
    final user = auth.teacherData?.teacher;
    // Use QR ID if available, otherwise fallback to DNI
    final qrData = user?.idQr ?? user?.dni ?? 'no-data';
    
    // Web Colors
    final Color cardBackground = const Color(0xFF2C2A4A);

    return Scaffold(
      appBar: AppBar(
        title: const Text("Carnet Digital"),
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              // FRONT OF CARD
              Container(
                width: 330,
                // height: 520, // Dynamic height slightly better for mobile adaptation
                constraints: const BoxConstraints(minHeight: 520),
                decoration: BoxDecoration(
                  color: cardBackground,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withOpacity(0.2), blurRadius: 20, offset: const Offset(0, 10))
                  ],
                ),
                child: Stack(
                  children: [
                     // Shape 1 (Top Left)
                    Positioned(
                      top: -100,
                      left: -150,
                      child: Container(
                        width: 350,
                        height: 350,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [Color(0xFF4F46E5), Color(0xFF0EA5E9)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        child: ClipOval(child: Container(color: Colors.white.withOpacity(0.0))), // Blur effect hard in Flutter stack without BackdropFilter restricted area
                      ),
                    ),
                    
                    // Shape 2 (Bottom Right)
                    Positioned(
                      bottom: -120,
                      right: -150,
                      child: Container(
                        width: 300,
                        height: 300,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [Color(0xFFD946EF), Color(0xFFF59E0B)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                      ),
                    ),

                    // Content
                    Padding(
                      padding: const EdgeInsets.all(25.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          // Header (Logo placeholder)
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.white24,
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: const Text("SIGEDO", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              )
                            ],
                          ),
                          const SizedBox(height: 40),
                          
                          // Profile Pic
                          Container(
                            padding: const EdgeInsets.all(4),
                            width: 148, 
                            height: 148,
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.8),
                              borderRadius: BorderRadius.circular(16), // Rounded square like web
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: (user?.foto != null) 
                                ? Image.network(user!.foto!, fit: BoxFit.cover)
                                : Container(color: Colors.grey, child: const Icon(Icons.person, size: 80, color: Colors.white)),
                            ),
                          ),
                          
                          const SizedBox(height: 20),
                          Text(
                            user?.name ?? "Nombre Docente",
                            style: const TextStyle(
                              color: Colors.white, 
                              fontSize: 24, // 1.5rem approx
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const Text(
                            "DOCENTE",
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 18,
                            ),
                          ),
                          
                          const SizedBox(height: 60),
                          
                          // QR Code (Simulating 'Reverso' functionality in same view for simplicity, like a flip)
                          // Or simply putting it at the bottom.
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: QrImageView(
                              data: qrData,
                              version: QrVersions.auto,
                              size: 160.0,
                              backgroundColor: Colors.white,
                            ),
                          ),
                           const SizedBox(height: 16),
                           Text(
                            "ID: ${user?.dni ?? '---'}",
                            style: const TextStyle(color: Colors.white, fontSize: 18, letterSpacing: 2),
                           ),
                        ],
                      ),
                    )
                  ],
                ),
              ),
              
              const SizedBox(height: 20),
              const Text("Presenta este código en el lector", style: TextStyle(color: Colors.grey)),
            ],
          ),
        ),
      ),
    );
  }
}
