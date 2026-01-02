import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../models/justification_type.dart';

class JustificationScreen extends StatefulWidget {
  const JustificationScreen({super.key});

  @override
  State<JustificationScreen> createState() => _JustificationScreenState();
}

class _JustificationScreenState extends State<JustificationScreen> {
  final _formKey = GlobalKey<FormState>();

  DateTime _startDate = DateTime.now();
  DateTime _endDate = DateTime.now();
  String? _selectedTypeId;
  final TextEditingController _reasonController = TextEditingController();

  File? _attachedFile;
  String? _attachedFileName;
  bool _isPdf = false;

  // Lista de tipos (mock por ahora, luego desde API)
  List<JustificationType> _types = [];
  bool _isLoadingTypes = true;

  @override
  void initState() {
    super.initState();
    _loadTypes();
  }

  Future<void> _loadTypes() async {
    try {
      final types = await Provider.of<AuthProvider>(
        context,
        listen: false,
      ).getJustificationTypes();
      if (!mounted) return;
      setState(() {
        _types = types;
        _isLoadingTypes = false;
      });
    } catch (e) {
      setState(() => _isLoadingTypes = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error cargando tipos: $e')));
    }
  }

  Future<void> _pickFile(bool isImage) async {
    if (isImage) {
      final picker = ImagePicker();
      final photo = await picker.pickImage(source: ImageSource.camera);
      if (photo != null) {
        setState(() {
          _attachedFile = File(photo.path);
          _attachedFileName = "Foto adjunta";
          _isPdf = false;
        });
      }
    } else {
      // Pick PDF or Image from gallery
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
      );

      if (result != null) {
        setState(() {
          _attachedFile = File(result.files.single.path!);
          _attachedFileName = result.files.single.name;
          _isPdf = result.files.single.extension == 'pdf';
        });
      }
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_attachedFile == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Debe adjuntar una evidencia.')),
      );
      return;
    }

    try {
      await Provider.of<AuthProvider>(
        context,
        listen: false,
      ).createJustification(
        typeId: int.parse(_selectedTypeId!),
        startDate: _startDate,
        endDate: _endDate,
        reason: _reasonController.text,
        file: _attachedFile!,
      );
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Solicitud enviada con éxito'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nueva Justificación')),
      body: _isLoadingTypes
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildDateSection(),
                    const SizedBox(height: 20),
                    DropdownButtonFormField<String>(
                      decoration: const InputDecoration(
                        labelText: 'Tipo de Justificación',
                        border: OutlineInputBorder(),
                      ),
                      items: _types
                          .map(
                            (t) => DropdownMenuItem(
                              value: t.id.toString(),
                              child: Text(t.nombre),
                            ),
                          )
                          .toList(),
                      onChanged: (v) => setState(() => _selectedTypeId = v),
                      validator: (v) => v == null ? 'Requerido' : null,
                    ),
                    const SizedBox(height: 20),
                    TextFormField(
                      controller: _reasonController,
                      decoration: const InputDecoration(
                        labelText: 'Motivo / Detalle',
                        border: OutlineInputBorder(),
                        alignLabelWithHint: true,
                      ),
                      maxLines: 4,
                      validator: (v) => v!.isEmpty ? 'Requerido' : null,
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      "Adjuntar Evidencia",
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.camera_alt),
                            label: const Text("Cámara"),
                            onPressed: () => _pickFile(true),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.attach_file),
                            label: const Text("Archivo"),
                            onPressed: () => _pickFile(false),
                          ),
                        ),
                      ],
                    ),
                    if (_attachedFile != null) ...[
                      const SizedBox(height: 10),
                      Chip(
                        label: Text(_attachedFileName ?? ""),
                        avatar: Icon(
                          _isPdf ? Icons.picture_as_pdf : Icons.image,
                        ),
                        onDeleted: () => setState(() => _attachedFile = null),
                      ),
                    ],
                    const SizedBox(height: 30),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _submit,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                        child: const Text("ENVIAR SOLICITUD"),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildDateSection() {
    return Row(
      children: [
        Expanded(
          child: InkWell(
            onTap: () async {
              final date = await showDatePicker(
                context: context,
                firstDate: DateTime(2020),
                lastDate: DateTime(2030),
                initialDate: _startDate,
              );
              if (date != null) setState(() => _startDate = date);
            },
            child: InputDecorator(
              decoration: const InputDecoration(
                labelText: 'Desde',
                border: OutlineInputBorder(),
              ),
              child: Text(
                "${_startDate.day}/${_startDate.month}/${_startDate.year}",
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: InkWell(
            onTap: () async {
              final date = await showDatePicker(
                context: context,
                firstDate: DateTime(2020),
                lastDate: DateTime(2030),
                initialDate: _endDate,
              );
              if (date != null) setState(() => _endDate = date);
            },
            child: InputDecorator(
              decoration: const InputDecoration(
                labelText: 'Hasta',
                border: OutlineInputBorder(),
              ),
              child: Text("${_endDate.day}/${_endDate.month}/${_endDate.year}"),
            ),
          ),
        ),
      ],
    );
  }
}
