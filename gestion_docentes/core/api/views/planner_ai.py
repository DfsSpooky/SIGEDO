import json
import logging
import google.generativeai as genai
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from core.models import Curso, BloqueHorario, Docente, Especialidad, Semestre, FranjaHoraria
from core.utils.responses import error_response, success_response, server_error_response
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- TOOLS (Functions Gemini can call) ---

def move_course_block(bloque_id: int, target_day: str, target_franja_id: int):
    """
    Mueve un bloque horario existente a un nuevo día y franja horaria.
    - target_day: Nombre del día (Lunes, Martes, Miércoles, Jueves, Viernes)
    - target_franja_id: ID de la franja horaria de inicio.
    """
    try:
        with transaction.atomic():
            bloque = BloqueHorario.objects.select_related('curso').get(id=bloque_id)
            franja = FranjaHoraria.objects.get(id=target_franja_id)
            
            # Validación básica de turno/especialidad (podemos ampliarla)
            bloque.dia = target_day
            bloque.franja_inicio = franja
            bloque.save()
            return {"status": "success", "message": f"Bloque de {bloque.curso.nombre} movido a {target_day} {franja.hora_inicio}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_teacher_availability(docente_id: int):
    """Obtiene la disponibilidad y el horario actual de un docente."""
    try:
        docente = Docente.objects.get(id=docente_id)
        bloques = BloqueHorario.objects.filter(curso__docente=docente)
        schedule = []
        for b in bloques:
            schedule.append({
                "curso": b.curso.nombre,
                "dia": b.dia,
                "inicio": b.franja_inicio.hora_inicio,
                "fin": b.franja_fin.hora_fin
            })
        return {
            "nombre": docente.nombre,
            "disponibilidad_preferida": docente.disponibilidad,
            "horario_actual": schedule
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Mapeo de herramientas para el modelo
tools = [move_course_block, get_teacher_availability]

def get_planner_context(especialidad_id=None, semestre_cursado=None):
    semestre_activo = Semestre.objects.filter(estado='ACTIVO').first()
    if not semestre_activo: return "No hay un semestre activo."
    
    context = f"Estado actual para el {semestre_activo.nombre}:\n"
    
    # Cursos
    query_cursos = Q(semestre=semestre_activo)
    if especialidad_id: query_cursos &= Q(especialidades__id=especialidad_id)
    if semestre_cursado: query_cursos &= Q(semestre_cursado=semestre_cursado)
        
    cursos = Curso.objects.filter(query_cursos).distinct()
    context += "CURSOS:\n"
    for c in cursos:
        context += f"- ID:{c.id}, {c.nombre} (H.Semanas:{c.horas_academicas_semanales}, Pend:{c.get_horas_pendientes()})\n"
    
    # Bloques
    bloques = BloqueHorario.objects.filter(curso__semestre=semestre_activo)
    if especialidad_id: bloques = bloques.filter(curso__especialidades__id=especialidad_id)
    
    context += "\nBLOQUES ASIGNADOS:\n"
    for b in bloques:
        context += f"- BloqueID:{b.id}, {b.curso.nombre}, {b.dia} {b.franja_inicio.hora_inicio} ({b.duracion_bloques}h)\n"
    
    # Franjas disponibles para referencia
    franjas = FranjaHoraria.objects.all().order_by('hora_inicio')
    context += "\nFRANJAS HORARIAS DISPONIBLES:\n"
    for f in franjas:
        context += f"- ID:{f.id}, {f.hora_inicio}-{f.hora_fin} ({f.turno})\n"

    return context

@staff_member_required
def api_planner_chat(request):
    if request.method != 'POST': return error_response("Método no permitido", status_code=405)
    if not GEMINI_API_KEY: return error_response("API Key de Gemini no configurada.", status_code=500)

    try:
        data = json.loads(request.body)
        user_message = data.get('message')
        history_in = data.get('history', [])
        esp_id = data.get('especialidad_id')
        sem_num = data.get('semestre_cursado')

        # Preparar historial para Gemini (formato esperado)
        # Gemini espera list of {role: ..., parts: [...]}
        
        context = get_planner_context(esp_id, sem_num)
        
        instruction = (
            "Eres el Asistente Inteligente del Planificador de Horarios de la Universidad (SIGEDO). "
            "Tu misión es ayudar a gestionar el horario. Puedes mover clases y consultar datos usando tus herramientas.\n"
            f"INFORMACIÓN ACTUAL:\n{context}\n\n"
            "REGLAS:\n"
            "1. Si el usuario pide mover una clase, usa 'move_course_block'.\n"
            "2. Sé preciso con los IDs de bloques y franjas.\n"
            "3. Tras usar una herramienta, informa al usuario del resultado."
        )

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            tools=tools,
            system_instruction=instruction
        )

        chat = model.start_chat(history=history_in, enable_automatic_function_calling=True)
        response = chat.send_message(user_message)

        # Actualizar historial
        new_history = history_in + [
            {"role": "user", "parts": [user_message]},
            {"role": "model", "parts": [response.text]}
        ]

        return success_response(data={
            "reply": response.text,
            "history": new_history
        })

    except Exception as e:
        logger.exception("Error en AI Assistant")
        return server_error_response(f"Error: {str(e)}")
