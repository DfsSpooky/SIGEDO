from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.utils import timezone
from datetime import timedelta
from django.views.generic import ListView, TemplateView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin

# Importaciones de modelos de otras apps
from apps.inventario.models import Activo
from core.models import BloqueHorario, Semestre

# Importación del modelo local
from .models import Reserva

class DisponibilidadEquiposView(LoginRequiredMixin, TemplateView):
    template_name = 'reservas/disponibilidad.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        docente = self.request.user
        today = timezone.now().date()

        if today.weekday() == 6: # Domingo
            start_of_week = today + timedelta(days=1)
        else:
            start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        fecha_str = self.request.GET.get('fecha', today.strftime('%Y-%m-%d'))
        try:
            fecha_seleccionada = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            if not (start_of_week <= fecha_seleccionada <= end_of_week):
                fecha_seleccionada = today
        except ValueError:
            fecha_seleccionada = today

        semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
        bloques_del_dia = []
        if semestre_activo:
            bloques_del_dia = BloqueHorario.objects.filter(
                curso__docente=docente,
                curso__semestre=semestre_activo,
                dia_semana=fecha_seleccionada.weekday()
            ).select_related('curso').order_by('horario_inicio')

        activos_disponibles = list(Activo.objects.filter(estado__in=['DISPONIBLE', 'ASIGNADO']))

        # Esta es una simplificación. La lógica original de franjas horarias
        # se mantiene pero ahora las dependencias están más claras.
        # En un refactor futuro, FranjaHoraria podría ser su propia app.
        from core.models import FranjaHoraria
        franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))

        bloques_con_disponibilidad = []
        for bloque in bloques_del_dia:
            try:
                start_index = franjas_horarias.index(bloque.franja_inicio)
                franjas_del_bloque_ids = [
                    franjas_horarias[i].id for i in range(start_index, start_index + bloque.duracion_bloques)
                    if i < len(franjas_horarias)
                ]
            except (ValueError, IndexError):
                continue

            activos_ocupados_ids = Reserva.objects.filter(
                fecha_reserva=fecha_seleccionada,
                estado__in=['RESERVADO', 'EN_USO'],
                franja_horaria_inicio_id__in=franjas_del_bloque_ids
            ).values_list('activo_id', flat=True)

            disponibles_para_bloque = [
                activo for activo in activos_disponibles if activo.id not in activos_ocupados_ids
            ]

            bloques_con_disponibilidad.append({
                'bloque': bloque,
                'activos_disponibles': disponibles_para_bloque
            })

        context['fecha_seleccionada_str'] = fecha_seleccionada.strftime('%Y-%m-%d')
        context['fecha_inicio_semana'] = start_of_week.strftime('%Y-%m-%d')
        context['fecha_fin_semana'] = end_of_week.strftime('%Y-%m-%d')
        context['bloques_con_disponibilidad'] = bloques_con_disponibilidad

        return context

    def post(self, request, *args, **kwargs):
        fecha_str = request.POST.get('fecha')
        redirect_url = reverse('reservas:disponibilidad')
        if fecha_str:
            redirect_url += f'?fecha={fecha_str}'

        try:
            bloque_id = request.POST.get('bloque_id')
            activo_id = request.POST.get('activo_id')
            docente = request.user

            if not all([bloque_id, activo_id, fecha_str]):
                messages.error(request, 'Información incompleta para procesar la reserva.')
                return HttpResponseRedirect(redirect_url)

            bloque = get_object_or_404(BloqueHorario, pk=bloque_id, curso__docente=docente)
            curso = bloque.curso
            activo = get_object_or_404(Activo, pk=activo_id)
            fecha = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()

            if bloque.dia_semana != fecha.weekday():
                messages.error(request, 'La fecha de la reserva no coincide con el día del bloque de horario.')
                return HttpResponseRedirect(redirect_url)

            from core.models import FranjaHoraria
            franjas_horarias = list(FranjaHoraria.objects.order_by('hora_inicio'))
            try:
                franja_inicio = bloque.franja_inicio
                start_index = franjas_horarias.index(franja_inicio)
                franja_fin = franjas_horarias[start_index + bloque.duracion_bloques - 1]
            except (ValueError, IndexError):
                messages.error(request, 'No se encontraron franjas horarias que coincidan con el horario del curso.')
                return HttpResponseRedirect(redirect_url)

            conflictos = Reserva.objects.filter(
                activo=activo,
                fecha_reserva=fecha,
                estado__in=['RESERVADO', 'EN_USO'],
                franja_horaria_inicio__hora_inicio__lt=franja_fin.hora_fin,
                franja_horaria_fin__hora_fin__gt=franja_inicio.hora_inicio
            ).exists()

            if conflictos:
                messages.error(request, 'El equipo ya no está disponible para el horario de este curso.')
            else:
                Reserva.objects.create(
                    activo=activo,
                    docente=docente,
                    curso=curso,
                    fecha_reserva=fecha,
                    franja_horaria_inicio=franja_inicio,
                    franja_horaria_fin=franja_fin
                )
                messages.success(request, f'Equipo "{activo.nombre}" reservado para el curso "{curso.nombre}" con éxito.')

        except (ValueError, Activo.DoesNotExist) as e:
            messages.error(request, f'Ocurrió un error al procesar la reserva: {e}')

        return HttpResponseRedirect(redirect_url)

class MisReservasView(LoginRequiredMixin, ListView):
    model = Reserva
    template_name = 'reservas/mis_reservas.html'
    context_object_name = 'reservas'
    paginate_by = 10

    def get_queryset(self):
        return Reserva.objects.filter(docente=self.request.user).select_related(
            'activo', 'activo__tipo', 'curso', 'franja_horaria_inicio', 'franja_horaria_fin'
        ).order_by('-fecha_reserva', '-franja_horaria_inicio__hora_inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        return context

@login_required
def cancelar_reserva(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, docente=request.user)

    hora_inicio_reserva = timezone.make_aware(
        timezone.datetime.combine(reserva.fecha_reserva, reserva.franja_horaria_inicio.hora_inicio)
    )
    if reserva.estado == 'RESERVADO' and hora_inicio_reserva > timezone.now():
        reserva.estado = 'CANCELADO'
        reserva.save()
        messages.success(request, 'La reserva ha sido cancelada.')
    else:
        messages.error(request, 'No es posible cancelar esta reserva (ya está en curso, finalizada o fue cancelada).')

    return redirect('reservas:mis_reservas')
