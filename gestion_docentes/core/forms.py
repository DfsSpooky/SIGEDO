from django import forms
from .models import Documento, SolicitudIntercambio, Curso, Docente, VersionDocumento

class DocumentoForm(forms.ModelForm):
    archivo = forms.FileField(label="Archivo (PDF o DOCX)", required=True)

    class Meta:
        model = Documento
        fields = ['titulo', 'tipo_documento'] # Mantenemos el campo aquí
        # --- INICIO DEL CAMBIO ---
        # Le decimos a Django que este campo no se debe ver, lo controlaremos con JS
        widgets = {
            'tipo_documento': forms.HiddenInput(),
        }
        # --- FIN DEL CAMBIO ---
    
    def clean_archivo(self):
        # ... (esta función se mantiene igual)
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            if not archivo.name.endswith(('.pdf', '.docx')):
                raise forms.ValidationError("Solo se permiten archivos PDF o DOCX.")
            if archivo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("El archivo no debe exceder 5MB.")
        return archivo
    
class VersionDocumentoForm(forms.ModelForm):
    class Meta:
        model = VersionDocumento
        fields = ['archivo']
        labels = {
            'archivo': 'Seleccionar nueva versión del archivo (PDF o DOCX)'
        }

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            if not archivo.name.endswith(('.pdf', '.docx')):
                raise forms.ValidationError("Solo se permiten archivos PDF o DOCX.")
            if archivo.size > 5 * 1024 * 1024:  # 5MB
                raise forms.ValidationError("El archivo no debe exceder 5MB.")
        return archivo

class SolicitudIntercambioForm(forms.ModelForm):
    docente_destino = forms.ModelChoiceField(queryset=Docente.objects.all())
    curso_destino = forms.ModelChoiceField(queryset=Curso.objects.all())

    class Meta:
        model = SolicitudIntercambio
        fields = ['docente_destino', 'curso_destino']

    def __init__(self, *args, **kwargs):
        curso_solicitante = kwargs.pop('curso_solicitante')
        super().__init__(*args, **kwargs)
        self.fields['docente_destino'].queryset = Docente.objects.filter(curso__carrera=curso_solicitante.carrera).distinct().exclude(id=curso_solicitante.docente.id)
        self.fields['curso_destino'].queryset = Curso.objects.filter(carrera=curso_solicitante.carrera).exclude(id=curso_solicitante.id)

    def clean(self):
        cleaned_data = super().clean()
        docente_destino = cleaned_data.get('docente_destino')
        curso_destino = cleaned_data.get('curso_destino')
        if curso_destino and curso_destino.docente != docente_destino:
            raise forms.ValidationError("El curso destino no pertenece al docente seleccionado.")
        return cleaned_data