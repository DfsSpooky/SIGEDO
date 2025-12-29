from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView
from django.utils import timezone
from datetime import datetime
from core.models import Asistencia

class RealTimeDashboardView(UserPassesTestMixin, TemplateView):
    template_name = "admin_dashboard_feed.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use localdate to respect TIME_ZONE settings (America/Lima)
        today = timezone.localdate()
        
        # 1. Fetch Course Attendance
        asistencias = list(Asistencia.objects.filter(fecha=today).select_related('docente', 'curso'))
        
        # 2. Fetch General Attendance
        from core.models import AsistenciaDiaria
        diarias = list(AsistenciaDiaria.objects.filter(fecha=today).select_related('docente'))
        
        # 3. Normalize General Attendance to match Template Interface
        # The template expects: obj.docente, obj.curso.nombre, obj.foto_entrada/salida, obj.hora_...
        class GeneralAttendanceWrapper:
            def __init__(self, obj):
                self.obj = obj
                self.docente = obj.docente
                self.fecha = obj.fecha
                self.hora_entrada = obj.hora_entrada
                self.hora_salida = obj.hora_salida
                self.foto_entrada = obj.foto_verificacion
                # Dummy curso object
                class DummyCurso:
                    nombre = "Control General"
                self.curso = DummyCurso()
                
        wrapped_diarias = [GeneralAttendanceWrapper(d) for d in diarias]
        
        # 4. Merge and Sort
        all_events = asistencias + wrapped_diarias
        # Sort by latest activity (entry or exit)
        # Helper to get a sortable time for events
        def get_event_time(event):
            # Prefer exit time, then entry time
            # If both are None (which shouldn't happen for valid attendance but possible in dirty data),
            # return a minimal aware datetime to sort it at the bottom.
            t = event.hora_salida or event.hora_entrada
            if t is None:
                return timezone.make_aware(datetime.min)
            return t
        
        all_events.sort(key=get_event_time, reverse=True)
        
        
        # 5. Context for Filters
        from core.models import Carrera, Curso
        context["carreras"] = Carrera.objects.all()
        # We might want only courses that have sessions today, or all courses. 
        # For simplicity in filters, let's provide all active courses or maybe just those from today's attendance?
        # A good UX is usually all active courses.
        context["cursos"] = Curso.objects.select_related('carrera').all()
        
        context["initial_events"] = all_events[:50]
        return context
