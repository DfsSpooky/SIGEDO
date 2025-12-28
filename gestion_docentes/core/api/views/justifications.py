from rest_framework import status, permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from core.models import Justificacion, TipoJustificacion
from core.api.serializers import JustificationSerializer, TipoJustificacionSerializer

class JustificationListView(generics.ListCreateAPIView):
    serializer_class = JustificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Justificacion.objects.filter(docente=self.request.user).order_by('-fecha_creacion')

    def perform_create(self, serializer):
        serializer.save(docente=self.request.user)

class TipoJustificacionListView(generics.ListAPIView):
    queryset = TipoJustificacion.objects.all()
    serializer_class = TipoJustificacionSerializer
    permission_classes = [permissions.IsAuthenticated]
