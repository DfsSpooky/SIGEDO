from django import forms
from core.models import Docente, Semestre, Curso, Especialidad

class DocenteCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    especialidades = forms.ModelMultipleChoiceField(
        queryset=Especialidad.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Especialidades"
    )

    class Meta:
        model = Docente
        fields = ('username', 'first_name', 'last_name', 'email', 'dni', 'disponibilidad', 'especialidades', 'foto')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
        return user

class DocenteChangeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Dejar en blanco para no cambiar la contraseña.", label="Contraseña")
    especialidades = forms.ModelMultipleChoiceField(
        queryset=Especialidad.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Especialidades"
    )

    class Meta:
        model = Docente
        fields = ('username', 'first_name', 'last_name', 'email', 'dni', 'disponibilidad', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'especialidades', 'foto')

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data["password"]:
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
        return user

class SemestreForm(forms.ModelForm):
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Inicio")
    fecha_fin = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Fecha de Fin")

    class Meta:
        model = Semestre
        fields = '__all__'

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = '__all__'
