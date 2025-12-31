import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../providers/auth_provider.dart';
import '../services/config_service.dart';
import 'forgot_password_screen.dart';
import 'main_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _canUseBiometric = false;
  String _institutionName = "SIGEDO";
  String? _logoUrl;

  @override
  void initState() {
    super.initState();
    _checkBiometricAvailability();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    final config = await ConfigService.getInstitutionConfig();
    if (config != null && mounted) {
      setState(() {
        if (config['nombre_institucion'] != null) {
          _institutionName = config['nombre_institucion'];
        }
        if (config['logo'] != null) {
          _logoUrl = config['logo'];
        }
      });
    }
  }

  Future<void> _checkBiometricAvailability() async {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final canCheck = await authProvider.isBiometricAvailable();
    final hasCredentials = await authProvider.hasStoredCredentials();

    if (mounted) {
      setState(() {
        _canUseBiometric = canCheck && hasCredentials;
      });
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleBiometricLogin() async {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final success = await authProvider.loginWithBiometrics();

    if (success && mounted) {
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute(builder: (_) => const MainScreen()));
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No se pudo verificar la identidad.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final googleBlue = const Color(0xFF1A73E8);
    final googleGrey = const Color(0xFF5F6368); // Body text
    final googleBlack = const Color(0xFF202124); // Headings

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // --- Logo ---
                  if (_logoUrl != null)
                    Image.network(
                      _logoUrl!,
                      height: 48,
                      errorBuilder: (_, __, ___) =>
                          Image.asset('assets/images/logo.png', height: 48),
                    )
                  else
                    Image.asset('assets/images/logo.png', height: 48),

                  const SizedBox(height: 24),

                  // --- Title ---
                  Text(
                    "Iniciar sesión",
                    style: GoogleFonts.roboto(
                      fontSize: 24,
                      fontWeight: FontWeight.w400,
                      color: googleBlack,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "Usa tu cuenta de $_institutionName",
                    textAlign: TextAlign.center,
                    style: GoogleFonts.roboto(
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      color: googleBlack,
                    ),
                  ),

                  const SizedBox(height: 40),

                  // --- Username Field ---
                  TextFormField(
                    controller: _usernameController,
                    style: GoogleFonts.roboto(fontSize: 16, color: googleBlack),
                    decoration: InputDecoration(
                      labelText: "Ingresa tu usuario",
                      labelStyle: TextStyle(color: googleGrey),
                      floatingLabelStyle: TextStyle(color: googleBlue),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: const BorderSide(color: Colors.grey),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: Colors.grey[300]!),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: googleBlue, width: 2),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        vertical: 16,
                        horizontal: 16,
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // --- Password Field ---
                  TextFormField(
                    controller: _passwordController,
                    obscureText: _obscurePassword,
                    style: GoogleFonts.roboto(fontSize: 16, color: googleBlack),
                    decoration: InputDecoration(
                      labelText: "Ingresa tu contraseña",
                      labelStyle: TextStyle(color: googleGrey),
                      floatingLabelStyle: TextStyle(color: googleBlue),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: const BorderSide(color: Colors.grey),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: Colors.grey[300]!),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: googleBlue, width: 2),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        vertical: 16,
                        horizontal: 16,
                      ),
                      suffixIcon: IconButton(
                        icon: Icon(
                          _obscurePassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                          color: googleGrey,
                        ),
                        onPressed: () => setState(
                          () => _obscurePassword = !_obscurePassword,
                        ),
                      ),
                    ),
                  ),

                  // --- Forgot Password ---
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: TextButton(
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => const ForgotPasswordScreen(),
                            ),
                          );
                        },
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 0),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          foregroundColor: googleBlue,
                        ),
                        child: Text(
                          "¿Has olvidado tu contraseña?",
                          style: GoogleFonts.roboto(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 48),

                  // --- Error Message ---
                  if (authProvider.errorMessage != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 24),
                      child: Row(
                        children: [
                          Icon(Icons.error, color: Colors.red[700], size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              authProvider.errorMessage!,
                              style: GoogleFonts.roboto(
                                color: Colors.red[700],
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // --- Actions Row ---
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // Biometric / Create Account styling space
                      if (_canUseBiometric)
                        TextButton.icon(
                          onPressed: _handleBiometricLogin,
                          icon: Icon(Icons.fingerprint, color: googleBlue),
                          label: Text(
                            "Biometría",
                            style: GoogleFonts.roboto(
                              color: googleBlue,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        )
                      else
                        const SizedBox.shrink(), // Empty spacer if no biometric
                      // Next Button
                      ElevatedButton(
                        onPressed: authProvider.isLoading
                            ? null
                            : () async {
                                final success = await authProvider.login(
                                  _usernameController.text.trim(),
                                  _passwordController.text.trim(),
                                );
                                if (success && mounted) {
                                  await _showBiometricSetupDialog();
                                  if (mounted) {
                                    Navigator.of(context).pushReplacement(
                                      MaterialPageRoute(
                                        builder: (_) => const MainScreen(),
                                      ),
                                    );
                                  }
                                }
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: googleBlue,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 12,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        child: authProvider.isLoading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : Text(
                                "Siguiente",
                                style: GoogleFonts.roboto(
                                  fontWeight: FontWeight.w500,
                                  fontSize: 14,
                                ),
                              ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _showBiometricSetupDialog() async {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final canCheck = await authProvider.isBiometricAvailable();
    if (!canCheck) return;
    if (!mounted) return;

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        title: Text(
          "Habilitar Biometría",
          style: GoogleFonts.roboto(fontWeight: FontWeight.w500),
        ),
        content: Text(
          "¿Quieres usar tu huella o rostro para iniciar sesión la próxima vez?",
          style: GoogleFonts.roboto(color: const Color(0xFF5F6368)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              "No",
              style: GoogleFonts.roboto(
                fontWeight: FontWeight.w600,
                color: const Color(0xFF5F6368),
              ),
            ),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await authProvider.saveCredentials(
                _usernameController.text.trim(),
                _passwordController.text.trim(),
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("Biometría habilitada")),
                );
              }
            },
            child: Text(
              "Habilitar",
              style: GoogleFonts.roboto(
                fontWeight: FontWeight.w600,
                color: const Color(0xFF1A73E8),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
