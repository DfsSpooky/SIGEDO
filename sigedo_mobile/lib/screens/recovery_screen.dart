import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:google_fonts/google_fonts.dart';

import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
// teacher_data.dart not needed if we access via AuthProvider.teacherData

class RecoveryScreen extends StatefulWidget {
  const RecoveryScreen({super.key});

  @override
  State<RecoveryScreen> createState() => _RecoveryScreenState();
}

class _RecoveryScreenState extends State<RecoveryScreen> {
  bool _isLoading = true;
  List<dynamic> _requests = [];

  @override
  void initState() {
    super.initState();
    _loadRequests();
  }

  Future<void> _loadRequests() async {
    try {
      final requests = await Provider.of<AuthProvider>(
        context,
        listen: false,
      ).getRecoveryRequests();
      if (!mounted) return;
      setState(() {
        _requests = requests;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error al cargar solicitudes: $e'),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    }
  }

  void _showCreateSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _CreateRecoverySheet(
        onSuccess: () {
          _loadRequests();
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Solicitud enviada exitosamente'),
              backgroundColor: Colors.green,
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pendingCount = _requests
        .where((r) => r['estado'] == 'PENDIENTE')
        .length;
    final approvedCount = _requests
        .where((r) => r['estado'] == 'APROBADO')
        .length;

    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6), // Light Grey
      appBar: AppBar(
        title: Text(
          'Recuperación de Clases',
          style: GoogleFonts.outfit(fontWeight: FontWeight.bold, fontSize: 20),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        iconTheme: const IconThemeData(color: Colors.black87),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadRequests,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildStatsHeader(pendingCount, approvedCount),
                          const SizedBox(height: 24),
                          Text(
                            "Mis Solicitudes",
                            style: GoogleFonts.outfit(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                              color: Colors.grey[800],
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                  ),
                  _requests.isEmpty
                      ? SliverFillRemaining(
                          hasScrollBody: false,
                          child: _buildEmptyState(),
                        )
                      : SliverList(
                          delegate: SliverChildBuilderDelegate(
                            (ctx, i) => _buildRequestCard(_requests[i]),
                            childCount: _requests.length,
                          ),
                        ),
                  const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
                ],
              ),
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateSheet,
        backgroundColor: AppTheme.primaryColor,
        icon: const Icon(Icons.add_rounded, color: Colors.white),
        label: Text(
          "Solicitar",
          style: GoogleFonts.outfit(
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        elevation: 4,
      ),
    );
  }

  Widget _buildStatsHeader(int pending, int approved) {
    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            "Pendientes",
            pending.toString(),
            Colors.orangeAccent,
            Icons.pending_actions,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _buildStatCard(
            "Aprobadas",
            approved.toString(),
            Colors.green,
            Icons.check_circle_outline,
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(
    String label,
    String value,
    Color color,
    IconData icon,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(icon, color: color, size: 24),
              Text(
                value,
                style: GoogleFonts.outfit(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: GoogleFonts.outfit(
              fontSize: 14,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Colors.blue[50],
            shape: BoxShape.circle,
          ),
          child: Icon(Icons.class_outlined, size: 60, color: Colors.blue[300]),
        ),
        const SizedBox(height: 24),
        Text(
          "Sin solicitudes recientes",
          style: GoogleFonts.outfit(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: Colors.grey[800],
          ),
        ),
        const SizedBox(height: 8),
        Text(
          "Si necesitas reprogramar una clase,\npuedes solicitarlo aquí.",
          textAlign: TextAlign.center,
          style: GoogleFonts.outfit(fontSize: 14, color: Colors.grey[500]),
        ),
      ],
    );
  }

  Widget _buildRequestCard(dynamic req) {
    final estado = req['estado'] ?? 'PENDIENTE';
    final curso = req['curso_nombre'] ?? 'Curso';
    final fechaProp = DateTime.parse(req['fecha_propuesta']);
    final fechaOriginal = DateTime.parse(req['fecha_a_recuperar']);

    Color statusColor;
    IconData statusIcon;
    switch (estado) {
      case 'APROBADO':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      case 'RECHAZADO':
        statusColor = Colors.red;
        statusIcon = Icons.cancel;
        break;
      default:
        statusColor = Colors.orange;
        statusIcon = Icons.hourglass_top;
    }

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
        border: Border(left: BorderSide(color: statusColor, width: 4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    curso,
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: Colors.black87,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Icon(statusIcon, size: 12, color: statusColor),
                      const SizedBox(width: 4),
                      Text(
                        estado,
                        style: GoogleFonts.outfit(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: statusColor,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildInfoRow(
              Icons.calendar_today,
              "Original",
              DateFormat('dd MMM yyyy').format(fechaOriginal),
            ),
            const SizedBox(height: 8),
            _buildInfoRow(
              Icons.next_plan,
              "Propuesta",
              DateFormat('dd MMM - hh:mm a').format(fechaProp),
            ),
            if (req['aula_solicitada'] != null) ...[
              const SizedBox(height: 8),
              _buildInfoRow(
                Icons.room,
                "Aula",
                req['aula_solicitada'].toString(),
              ), // Assuming ID or Name
            ],
            if (req['observaciones'] != null &&
                req['observaciones'].isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.yellow[50],
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.yellow.shade200),
                ),
                child: Text(
                  "Nota: ${req['observaciones']}",
                  style: GoogleFonts.outfit(
                    fontSize: 12,
                    color: Colors.orange[800],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 14, color: Colors.grey[400]),
        const SizedBox(width: 6),
        Text(
          "$label: ",
          style: GoogleFonts.outfit(fontSize: 12, color: Colors.grey[600]),
        ),
        Text(
          value,
          style: GoogleFonts.outfit(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Colors.black87,
          ),
        ),
      ],
    );
  }
}

class _CreateRecoverySheet extends StatefulWidget {
  final VoidCallback onSuccess;
  const _CreateRecoverySheet({required this.onSuccess});

  @override
  State<_CreateRecoverySheet> createState() => _CreateRecoverySheetState();
}

class _CreateRecoverySheetState extends State<_CreateRecoverySheet> {
  final _formKey = GlobalKey<FormState>();
  int? _selectedCourseId;
  DateTime _dateToRecover = DateTime.now();
  DateTime _proposedDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _proposedTime = const TimeOfDay(hour: 18, minute: 00);
  int _durationMinutes = 90;
  final _reasonController = TextEditingController();
  bool _submitting = false;

  @override
  Widget build(BuildContext context) {
    final teacherData = Provider.of<AuthProvider>(
      context,
      listen: false,
    ).teacherData;
    final courses = teacherData?.courses ?? [];

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(24),
          topRight: Radius.circular(24),
        ),
      ),
      padding: EdgeInsets.only(
        top: 24,
        left: 24,
        right: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.indigo[50],
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.edit_calendar,
                      color: Colors.indigo,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          "Nueva Solicitud",
                          style: GoogleFonts.outfit(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          "Completa los datos para reprogramar",
                          style: GoogleFonts.outfit(
                            fontSize: 12,
                            color: Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Course Selector
              DropdownButtonFormField<int>(
                decoration: InputDecoration(
                  labelText: 'Curso a Recuperar',
                  labelStyle: GoogleFonts.outfit(fontSize: 14),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  prefixIcon: const Icon(Icons.book_outlined),
                ),
                items: courses
                    .map(
                      (c) => DropdownMenuItem(
                        value: c.id,
                        child: Text(c.name, overflow: TextOverflow.ellipsis),
                      ),
                    )
                    .toList(),
                onChanged: (val) => setState(() => _selectedCourseId = val),
                validator: (v) => v == null ? 'Seleccione un curso' : null,
              ),
              const SizedBox(height: 16),

              // Fechas Row
              Row(
                children: [
                  Expanded(
                    child: _buildDatePicker(
                      "Fecha Original",
                      _dateToRecover,
                      Icons.calendar_month,
                      (picked) => setState(() => _dateToRecover = picked),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildDatePicker(
                      "Propuesta",
                      _proposedDate,
                      Icons.next_plan_outlined,
                      (picked) => setState(() => _proposedDate = picked),
                      startFromNow: true,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Time & Duration Row
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: () async {
                        final picked = await showTimePicker(
                          context: context,
                          initialTime: _proposedTime,
                        );
                        if (picked != null) {
                          setState(() => _proposedTime = picked);
                        }
                      },
                      child: InputDecorator(
                        decoration: InputDecoration(
                          labelText: 'Hora Inicio',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          prefixIcon: const Icon(Icons.access_time),
                        ),
                        child: Text(
                          _proposedTime.format(context),
                          style: GoogleFonts.outfit(),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      initialValue: '90',
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: 'Minutos',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        prefixIcon: const Icon(Icons.timer_outlined),
                      ),
                      onChanged: (v) =>
                          _durationMinutes = int.tryParse(v) ?? 90,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Reason
              TextFormField(
                controller: _reasonController,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: 'Motivo de la recuperación',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  prefixIcon: const Icon(Icons.notes),
                ),
                validator: (v) =>
                    v == null || v.isEmpty ? 'Escriba un motivo' : null,
              ),
              const SizedBox(height: 24),

              // Submit Button
              ElevatedButton(
                onPressed: _submitting ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryColor,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 0,
                ),
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : Text(
                        "Enviar Solicitud",
                        style: GoogleFonts.outfit(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDatePicker(
    String label,
    DateTime date,
    IconData icon,
    Function(DateTime) onPick, {
    bool startFromNow = false,
  }) {
    return InkWell(
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: date,
          firstDate: startFromNow ? DateTime.now() : DateTime(2024),
          lastDate: DateTime(2026),
        );
        if (picked != null) {
          onPick(picked);
        }
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          prefixIcon: Icon(icon, size: 20),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 16,
          ),
        ),
        child: Text(
          DateFormat('dd/MM/yy').format(date),
          style: GoogleFonts.outfit(fontSize: 14),
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (_formKey.currentState!.validate()) {
      setState(() => _submitting = true);
      try {
        // Combine Date + Time
        final fullProposedDate = DateTime(
          _proposedDate.year,
          _proposedDate.month,
          _proposedDate.day,
          _proposedTime.hour,
          _proposedTime.minute,
        );

        await Provider.of<AuthProvider>(
          context,
          listen: false,
        ).createRecoveryRequest(
          courseId: _selectedCourseId!,
          dateToRecover: _dateToRecover,
          proposedDate: fullProposedDate,
          durationMinutes: _durationMinutes,
          reason: _reasonController.text,
        );

        if (mounted) {
          Navigator.pop(context);
          widget.onSuccess();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text("Error: $e")));
        }
      } finally {
        if (mounted) {
          setState(() => _submitting = false);
        }
      }
    }
  }
}
