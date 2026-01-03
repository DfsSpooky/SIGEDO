import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import 'pdf_viewer_screen.dart';

class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({super.key});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen>
    with AutomaticKeepAliveClientMixin {
  // Keep state alive
  late Future<List<dynamic>> _documentsFuture; // Cache the future

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    // Load initial data
    _documentsFuture = _fetchDocuments();
  }

  Future<List<dynamic>> _fetchDocuments() {
    final api = Provider.of<AuthProvider>(context, listen: false).api;
    return api.getDocuments();
  }

  Future<void> _refresh() async {
    setState(() {
      _documentsFuture = _fetchDocuments();
    });
    await _documentsFuture;
  }

  Future<void> _pickAndUpload(int typeId, String title) async {
    // 1. Pick File
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'doc', 'docx', 'jpg', 'png'],
    );

    if (result != null && result.files.single.path != null) {
      if (!mounted) return;
      File file = File(result.files.single.path!);

      // Confirm
      bool? confirm = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text("Confirmar subida"),
          content: Text(
            "¿Deseas subir el archivo '${result.files.single.name}' para '$title'?",
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text("Cancelar"),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text("Subir"),
            ),
          ],
        ),
      );

      if (confirm == true && mounted) {
        // Show loading dialog implementation
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (c) => const Center(child: CircularProgressIndicator()),
        );

        final api = Provider.of<AuthProvider>(context, listen: false).api;
        bool success = await api.uploadDocument(typeId: typeId, file: file);

        if (!mounted) return;

        if (mounted) {
          Navigator.pop(context); // Close loader

          if (success) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text("Documento subido exitosamente"),
                backgroundColor: Colors.green,
              ),
            );
            _refresh();
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text("Error al subir documento"),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: const Text(
          "Gestión Documental",
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: Colors.black87,
      ),
      body: FutureBuilder<List<dynamic>>(
        future: _documentsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final sections = snapshot.data ?? [];

          if (sections.isEmpty &&
              snapshot.connectionState == ConnectionState.done) {
            return _buildEmptyState();
          }

          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.builder(
              padding: const EdgeInsets.only(bottom: 80, top: 16),
              itemCount: sections.length,
              itemBuilder: (context, index) {
                final section = sections[index];
                final String title = section['sectionTitle'] ?? 'Otros';
                final String statusKey = section['statusKey'] ?? 'DEFAULT';
                final List documents = section['documents'] ?? [];

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: _getColorForState(
                                statusKey,
                              ).withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              _getIconForState(statusKey),
                              color: _getColorForState(statusKey),
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Text(
                            title,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.5,
                              color: Colors.black87,
                            ),
                          ),
                          const Spacer(),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              border: Border.all(color: Colors.grey.shade300),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              "${documents.length}",
                              style: TextStyle(
                                color: Colors.grey[700],
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    // List
                    ...documents.map(
                      (doc) => _buildDocumentCard(context, doc, statusKey),
                    ),
                    const SizedBox(height: 12),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget _buildDocumentCard(
    BuildContext context,
    dynamic doc,
    String statusKey,
  ) {
    final isDummy = doc['isDummy'] == true;
    final state = doc['estado'] ?? 'UNKNOWN';
    final int? tipoId = doc['tipoId'];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () {
            if (isDummy && tipoId != null) {
              _pickAndUpload(tipoId, doc['titulo']);
            } else if (state == 'OBSERVADO' && tipoId != null) {
              // Allow re-upload for Observed documents
              _pickAndUpload(tipoId, doc['titulo']);
            } else {
              if (doc['url'] != null) {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => PdfViewerScreen(
                      url: doc['url'],
                      title: doc['titulo'] ?? 'Documento',
                    ),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text("Este documento no tiene archivo asociado."),
                  ),
                );
              }
            }
          },
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                // Icon Box
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: isDummy
                        ? Colors.grey[100]
                        : _getColorForState(state).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(
                    isDummy
                        ? Icons.cloud_upload_outlined
                        : Icons.description_outlined,
                    color: isDummy
                        ? Colors.grey[500]
                        : _getColorForState(state),
                    size: 26,
                  ),
                ),

                const SizedBox(width: 16),

                // Content
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doc['titulo'] ?? 'Documento',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                          color: isDummy ? Colors.grey[700] : Colors.black87,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          if (!isDummy)
                            Icon(
                              Icons.calendar_today,
                              size: 12,
                              color: Colors.grey[500],
                            ),
                          if (!isDummy) const SizedBox(width: 4),
                          Text(
                            isDummy
                                ? "Requiere subida"
                                : "${doc['fechaSubida'] ?? '--'}",
                            style: TextStyle(
                              color: Colors.grey[500],
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Status Pill or Arrow
                if (isDummy)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.blue[50],
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: Colors.blue.withValues(alpha: 0.2),
                      ),
                    ),
                    child: const Text(
                      "Subir",
                      style: TextStyle(
                        color: Colors.blue,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  )
                else
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: _getColorForState(state),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          state,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      if (state == 'OBSERVADO')
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Text(
                            "Corregir",
                            style: TextStyle(
                              color: Colors.orange[700],
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
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
    );
  }

  Widget _buildEmptyState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.folder_open, size: 80, color: Colors.grey),
          SizedBox(height: 20),
          Text(
            "No tienes documentos",
            style: TextStyle(color: Colors.grey, fontSize: 18),
          ),
        ],
      ),
    );
  }

  Color _getColorForState(String state) {
    switch (state) {
      case 'APROBADO':
        return const Color(0xFF10B981); // Emerald
      case 'OBSERVADO':
        return const Color(0xFFEF4444); // Red
      case 'EN_REVISION':
        return const Color(0xFF3B82F6); // Blue
      case 'PENDIENTE':
        return Colors.grey;
      case 'RECIBIDO':
        return const Color(0xFFF59E0B); // Amber
      case 'VENCIDO':
        return const Color(0xFF8B5CF6); // Purple
      default:
        return Colors.grey;
    }
  }

  IconData _getIconForState(String state) {
    switch (state) {
      case 'APROBADO':
        return Icons.check_circle_outline;
      case 'OBSERVADO':
        return Icons.error_outline;
      case 'EN_REVISION':
        return Icons.hourglass_top;
      case 'PENDIENTE':
        return Icons.assignment_late_outlined;
      case 'RECIBIDO':
        return Icons.file_present;
      default:
        return Icons.folder_open;
    }
  }
}
