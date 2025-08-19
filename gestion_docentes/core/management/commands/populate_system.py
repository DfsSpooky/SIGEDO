import random
import re
from django.core.management.base import BaseCommand
from datetime import date, time
from django.contrib.auth import get_user_model
from django.db import transaction
from core.models import (
    Carrera, Especialidad, Curso, Semestre, ConfiguracionInstitucion,
    Grupo, Documento, TipoDocumento, Anuncio, FranjaHoraria, Docente
)

User = get_user_model()

# Datos proporcionados por el usuario
SCHEDULE_DATA = """
Programa,Semestre,Día,Hora,Turno,Curso,Docente
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,11.20 – 12.10,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,8.00 – 8.50,Mañana,Teoría de Números,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,10.30 – 11.20,Mañana,Geometría no Euclidiana,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre V,LUNES,4.40 – 5.30,Tarde,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,3.00 – 3.50,Tarde,Teoría de Juegos,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Análisis Real,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,3.00 – 3.50,Tarde,Geometría Analítica Vectorial,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,LUNES,5.30 – 6.20,Tarde/Noche,Biofísica,Wilmer Guevara Vásquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,8.00 – 8.50,Mañana,Calculo Diferencial,Wilmer Guevara Vasquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre III,MARTES,9.40 – 10.30,Mañana,Fundamentos de Programación,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,12.10 – 13.00,Mañana,Geometría no Euclidiana,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,3.00 – 3.50,Tarde,Física II,Wilmer Guevara Vasquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre V,MARTES,4.40 – 5.30,Tarde,Ecuaciones Diferenciales,Tito Armando Rivera Espinoza
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,7.10 – 8.00,Mañana,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,3.00 – 3.50,Tarde,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre VII,MARTES,4.40 – 5.30,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,7.10 – 8.00,Mañana,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MARTES,7.10 – 8.00,Mañana,Estructuras Algebraicas,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre I,MIERCOLES,9.40 – 10.30,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,11.20 – 12.10,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,3.30 – 4.20,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,8.00 – 8.50,Mañana,Sociología de la Educación Dr.Anibal Carbajal Leandro,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,10.30 – 11.20,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre V,MIERCOLES,5.30 – 6.20,Tarde/Noche,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,3.00 – 3.50,Tarde,Análisis Real,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre VII,MIERCOLES,5.30 – 6.20,Tarde/Noche,Sistemas Numéricos,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,3.00 – 3.50,Tarde,Geometría Analítica Vectorial,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,MIERCOLES,5.30 – 6.20,Tarde/Noche,Biofísica,Wilmer Guevara Vasquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,8.00 – 8.50,Mañana,Fundamentos de Programación,Clodoaldo Ramos Pando
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,10.30 – 11.20,Mañana,Calculo Diferencial,Wilmer Guevara Vasquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,3.00 – 3.50,Tarde,Ecuaciones Diferenciales,Tito Armando Rivera Espinoza
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre V,JUEVES,5.30 – 6.20,Tarde/Noche,Física II,Wilmer Guevara Vasquez
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,JUEVES,3.00 – 3.50,Tarde,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,8.00 – 8.50,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,10.30 – 11.20,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,12.10 – 1.00,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,8.00 – 8.50,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,10.30 – 11.20,Mañana,Filosofía de la Educación,
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,Semestre V,VIERNES,5.30 – 6.20,Tarde/Noche,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,7.10 – 8.00,Mañana,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,3.00 – 3.50,Tarde,Estructuras Algebraicas,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE MATEMÁTICA,,VIERNES,5.30 – 6.20,Tarde/Noche,Epistemología de la Matemática Física,Víctor Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,11.20 – 12.10,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,8.00 – 8.50,Mañana,Metodología de la programación,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,11.20 – 12.10,Mañana,Dibujo y Diseño CAD,Percy Zavala
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre V,LUNES,4.40 – 5.30,Tarde,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,3.00 – 3.50,Tarde,Análisis y  de software ,Miguel Ventura
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Telecomunicaciones II.,Percy Zavala
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,3.00 – 3.50,Tarde,Desarrollo de Software.,Percy Zavala
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,LUNES,5.30 – 6.20,Tarde/Noche,Sistema de transmisión de datos,Juan Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,8.00 – 8.50,Mañana,Metodología de la programación,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,8.50 – 9.40,Mañana,Sistemas operativos,Miguel Ventura Janampa
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,11.20 – 12.10,Mañana,Electrónica Básica,Juan Carbajal Mayhua
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,3.00 – 3.50,Tarde,Telecomunicaciones I,Miguel Ventura Janampa
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre V,MARTES,4.40 – 5.30,Tarde,Electrónica digital,Juan Carbajal Mayhua
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,7.10 – 8.00,Mañana,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,3.00 – 3.50,Tarde,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre VII,MARTES,4.40 – 5.30,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,7.10 – 8.00,Mañana,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,9.40 – 10.30,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,11.20 – 12.10,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,3.30 – 4.20,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,8.00 – 8.50,Mañana,Sociología de la Educación Dr.Anibal Carbajal Leandro,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,10.30 – 11.20,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre V,MIERCOLES,5.30 – 6.20,Tarde/Noche,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,3.00 – 3.50,Tarde,Telecomunicaciones II.,Percy Zavala Rosales
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre VII,MIERCOLES,4.40 – 5.30,Tarde,Robótica educativa I,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,3.00 – 3.50,Tarde,Sistema de transmisión de datos,Juan Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre IX,MIERCOLES,4.40 – 5.30,Tarde,Desarrollo de Software.,Percy Zavala
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,MIERCOLES,7.10 – 8.00,Mañana,Telecomunicaciones III,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,8.00 – 8.50,Mañana,Electrónica Básica,Juan Carbajal Mayhua
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre III,JUEVES,9.40 – 10.30,Mañana,Sistemas operativos,Miguel Ventura Janampa
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,12.10 – 13.00,Mañana,Dibujo y Diseño CAD,Percy Zavala
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,3.00 – 3.50,Tarde,Electrónica digital,Juan Carbajal Mayhua
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre V,JUEVES,4.40 – 5.30,Tarde,Telecomunicaciones I,Miguel Ventura Janampa
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,JUEVES,3.00 – 3.50,Tarde,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,8.00 – 8.50,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,10.30 – 11.20,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,12.10 – 1.00,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,8.00 – 8.50,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,10.30 – 11.20,Mañana,Filosofía de la Educación,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre V,VIERNES,5.30 – 6.20,Tarde/Noche,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,7.10 – 8.00,Mañana,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,Semestre VII,VIERNES,4.40 – 5.30,Tarde,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE TECNOLOGÍA INFORMÁTICA Y TELECOMUNICACIONES,,VIERNES,3.00 – 3.50,Tarde,Telecomunicaciones III,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,11.20 – 12.10,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,8.00 – 8.50,Mañana,Educación para la salud,Rómulo Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,10.30 – 11.20,Mañana,Botánica,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre V,LUNES,4.40 – 5.30,Tarde,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,3.00 – 3.50,Tarde,Nutrición,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre VII,LUNES,4.40 – 5.30,Tarde,Anatomia y fisiología Humana,Rómula Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,3.00 – 3.50,Tarde,Laboratorio de Biología y Química,Rómulo Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre IX,LUNES,4.40 – 5.30,Tarde,Fisico Químico,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,LUNES,6.20 – 7.10,Tarde/Noche,Microbiología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,8.00 – 8.50,Mañana,Física I,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,10.30 – 11.20,Mañana,Química General I,Luis Murga Paulino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,12.10 – 13.00,Mañana,Botánica,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,3.00 – 3.50,Tarde,Citología y Genética,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre V,MARTES,5.30 – 6.20,Tarde/Noche,Química Inorgánica,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,7.10 – 8.00,Mañana,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,3.00 – 3.50,Tarde,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre VII,MARTES,4.40 – 5.30,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,7.10 – 8.00,Mañana,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,9.40 – 10.30,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,11.20 – 12.10,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,3.30 – 4.20,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,8.00 – 8.50,Mañana,Sociología de la Educación Dr.Anibal Carbajal Leandro,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,10.30 – 11.20,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre V,MIERCOLES,5.30 – 6.20,Tarde/Noche,Didáctica General,Lilia Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,3.00 – 3.50,Tarde,Anatomia y fisiología Humana,Rómula Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre VII,MIERCOLES,5.30 – 6.20,Tarde/Noche,Nutrición,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,3.00 – 3.50,Tarde,Fisico Químico,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre IX,MIERCOLES,4.40 – 5.30,Tarde,Microbiología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,MIERCOLES,6.20 – 7.10,Tarde/Noche,Laboratorio de Biología y Química,Rómulo Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,8.00 – 8.50,Mañana,Matemática Básica,Luis Albornoz Dávila
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,10.30 – 11.20,Mañana,Realidad Nacional,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,8.00 – 8.50,Mañana,Educación para la salud,Rómulo Castillo Arellano
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre III,JUEVES,9.40 – 10.30,Mañana,Física I,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,12.10 – 13.00,Mañana,Química General I,Luis Murga Paulino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,3.00 – 3.50,Tarde,Química Inorgánica,Emilia Misari Chuquipoma
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre V,JUEVES,4.40 – 5.30,Tarde,Citología y Genética,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Armando Carhuachin Marcelo
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Liz Bernaldo Faustino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,JUEVES,3.00 – 3.50,Tarde,Tutoría Familia y Comunidad,Lucy Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Abel Roblés Carbajal
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,8.00 – 8.50,Mañana,Ecología,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,10.30 – 11.20,Mañana,Psicología del Desarrollo Humano,Luis Lobardi Palomino
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,12.10 – 1.00,Mañana,Metodolos de Estudio de Trabajo Universitario,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,8.00 – 8.50,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,10.30 – 11.20,Mañana,Filosofía de la Educación,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Alfredo Siuce Bonifacio
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,Semestre V,VIERNES,5.30 – 6.20,Tarde/Noche,Pedagogía de la Diversidad e Inclusión,
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,7.10 – 8.00,Mañana,Psicología del Aprendizaje,Cabrera Caso
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE BIOLOGÍA Y QUÍMICA,,VIERNES,3.00 – 3.50,Tarde,Química Analítica Cualitativa y Cuantitativa,Luis Murga Paulino
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,11.20 – 12.10,Mañana,Ecología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,8.00 – 8.50,Mañana,Fonética y Fonología Española,U. Espinoza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,10.30 – 11.20,Mañana,Teoría Literaria,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre V,LUNES,5.30 – 6.20,Tarde/Noche,Psicología del Aprendizaje,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,7.10 – 8.00,Mañana,Pedagogía de la Diversidad e Inclusión Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Lenguaje Audiovisual Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,3.00 – 3.50,Tarde,Didáctica de la Comunicación,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,LUNES,5.30 – 6.20,Tarde/Noche,Literatura Latinoamericana,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,3.30 – 4.20,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,8.00 – 8.50,Mañana,Teoría Literaria,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre III,MARTES,9.40 – 10.30,Mañana,Taller de ortografía,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,11.20 – 12.10,Mañana,Morfosintásis I,Teofilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,3.00 – 3.50,Tarde,Literatura Española,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre V,MARTES,4.40 – 5.30,Tarde,Análisis e interpretación de textos Literarios,Pablo La Madrid Vivar
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre VII,MARTES,4.40 – 5.30,Tarde,Literatura Peruana II.,
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,7.10 – 8.00,Mañana,Calidad Educativa,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría Familia y Comunidad,Luis Lombardi palomino
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,8.00 – 8.50,Mañana,Ecología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,10.30 – 11.20,Mañana,Metodolos de Estudio de Trabajo Universitario,Teófilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,12.10 – 1.00,Mañana,Idiomas: Inglés Básico,Carolina Ninahuaman
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,8.00 – 8.50,Mañana,Teoría de la educación,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,10.30 – 11.20,Mañana,Sociología de la Educación,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre V,MIERCOLES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,7.10 – 8.00,Mañana,Didáctica General,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,3.00 – 3.50,Tarde,Lecturas Linguísticas,José Davila Inocente
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre VII,MIERCOLES,5.30 – 6.20,Tarde/Noche,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,3.00 – 3.50,Tarde,Literatura Latinoamericana,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,MIERCOLES,5.30 – 6.20,Tarde/Noche,Prágmática,Pablo La Madrid Vivar
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,8.00 – 8.50,Mañana,Comunicación Oral y Escrita,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,9.40 – 10.30,Mañana,Realidad Nacional,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,11.20 – 12.10,Mañana,Matemática Básica,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,8.00 – 8.50,Mañana,Morfosintásis I,Teofilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre III,JUEVES,9.40 – 10.30,Mañana,Taller de ortografía,Isabel Delzo Calderón
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,11.20 – 12.10,Mañana,Fonética y Fonología Española,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,3.00 – 3.50,Tarde,Análisis e interpretación de textos Literarios,Pablo La Madrid Vivar
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre V,JUEVES,5.30 – 6.20,Tarde/Noche,Literatura Española,Moisés Agustín Cristobal
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,3.00 – 3.50,Tarde,Literatura Peruana II.,
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,3.00 – 3.50,Tarde,Tutoría Familia y Comunidad,Luis Lombardi palomino
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,JUEVES,6.20 – 7.10,Tarde/Noche,Didáctica de la Comunicación,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,Carolina Ninahuaman
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,9.40 – 10.30,Mañana,Psicología del Desarrollo Humano,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,11.20 – 12.10,Mañana,Metodolos de Estudio de Trabajo Universitario,Teófilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,8.00 – 8.50,Mañana,Teoría de la educación,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,3.00 – 3.50,Tarde,Didáctica General,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,Semestre V,VIERNES,5.30 – 6.20,Tarde/Noche,Pedagogía de la Diversidad e Inclusión Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Matos Atanacio
A    PROGRAMA DE ESTUDIOS DE COMUNICACIÓN Y LITERATURA,,VIERNES,3.00 – 3.50,Tarde,Lingüística del Texto Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,11.20 – 12.10,Mañana,Ecología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,8.00 – 8.50,Mañana,Comprensión y producción escrita en inglés,Luis Martel Reyes
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,11.20 – 12.10,Mañana,Lingüística General,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,3.00 – 3.50,Tarde,Teoría y Diseño Curricular,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre V,LUNES,5.30 – 6.20,Tarde/Noche,Psicología del Aprendizaje,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,7.10 – 8.00,Mañana,Pedagogía de la Diversidad e Inclusión Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Francés V,
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,3.00 – 3.50,Tarde,Comprensión y producción escrita en inglés II.,Luis Martel Reyes
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,5.30 – 6.20,Tarde/Noche,Fonética del Inglés,Elena Campos
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,LUNES,7.10 – 8.00,Mañana,Fonética del inglés,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,12.10 – 1.00,Mañana,Comunicación Oral y Escrita,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,3.30 – 4.20,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,8.00 – 8.50,Mañana,Francés I,Elena Campos Barbié
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,10.30 – 11.20,Mañana,Inglés II,Carolina Ninahuanca Martinez
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,3.00 – 3.50,Tarde,Inglés IV,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre V,MARTES,5.30 – 6.20,Tarde/Noche,Francés III.,Elena Campos Barbié
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Matos atanacio
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre VII,MARTES,4.40 – 5.30,Tarde,Inglés VI.,Luis Martel
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,7.10 – 8.00,Mañana,Calidad Educativa,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría Familia y Comunidad,Luis Lombardi palomino
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,8.00 – 8.50,Mañana,Ecología,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,10.30 – 11.20,Mañana,Metodolos de Estudio de Trabajo Universitario,Teófilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,12.10 – 1.00,Mañana,Idiomas: Inglés Básico,Carolina Ninahuaman
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,8.00 – 8.50,Mañana,Teoría de la educación,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,10.30 – 11.20,Mañana,Sociología de la Educación,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre V,MIERCOLES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Julio Carhuaricra Meza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,7.10 – 8.00,Mañana,Didáctica General,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,3.00 – 3.50,Tarde,Francés V,
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre VII,MIERCOLES,5.30 – 6.20,Tarde/Noche,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,3.00 – 3.50,Tarde,Fonética del Inglés,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,MIERCOLES,5.30 – 6.20,Tarde/Noche,Inglés VIII,Carolina Ninahuanca Martinez
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,8.00 – 8.50,Mañana,Comunicación Oral y Escrita,Ulises Espinoza Apolinario
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,9.40 – 10.30,Mañana,Realidad Nacional,Edith Zela Sanchez
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,11.20 – 12.10,Mañana,Matemática Básica,Werner Surichaqui Hidalgo
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,8.00 – 8.50,Mañana,Inglés II,Carolina Ninahuanca Martinez
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre III,JUEVES,9.40 – 10.30,Mañana,Francés I,Elena Campos Barbié
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,12.10 – 13.00,Mañana,Lingüística General,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,3.00 – 3.50,Tarde,Francés III.,Elena Campos Barbié
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre V,JUEVES,5.30 – 6.20,Tarde/Noche,Inglés IV,Julio Lagos Huere
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,3.00 – 3.50,Tarde,Inglés VI.,Luis Martel
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Anibal Carbajal Leandro
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,7.10 – 8.00,Mañana,Manejo de Laboratorio II Contrato/Traducción en Inglés II,Luis Martel Reyes
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,3.00 – 3.50,Tarde,Tutoría Familia y Comunidad,Luis Lombardi palomino
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,JUEVES,6.20 – 7.10,Tarde/Noche,Fonética del Inglés,Elena Campos
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,Carolina Ninahuaman
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,9.40 – 10.30,Mañana,Psicología del Desarrollo Humano,Nora Campos Hinostroza
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,11.20 – 12.10,Mañana,Metodolos de Estudio de Trabajo Universitario,Teófilo Valentin Melgarejo
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,8.00 – 8.50,Mañana,Teoría de la educación,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,10.30 – 11.20,Mañana,Filosofía de la Educación Orlando campos Salvatierra,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,3.00 – 3.50,Tarde,Didáctica General,Raúl Malpartida Lovatón
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,Semestre V,VIERNES,5.30 – 6.20,Tarde/Noche,Pedagogía de la Diversidad e Inclusión Contrato,Desconocido
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Matos atanacio
A    PROGRAMA DE ESTUDIOS LENGUAS EXTRANJERAS: INGLÉS FRANCÉS,,VIERNES,3.00 – 3.50,Tarde,Inglés VIII,Carolina Ninahuanca Martinez
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Eva Elsa Condor Surichaqui
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,11.20 – 12.10,Mañana,Ecología Dra Lucy Ricaldi Canchihuaman,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,8.00 – 8.50,Mañana,Historia de América y el Mundo I,Eduardo Marino Pacheco Peña
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,10.30 – 11.20,Mañana,Perú Prehispánico,Ana María Navarro Porrás
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre V,LUNES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Sanyorei Porras Cosme
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,7.10 – 8.00,Mañana,Pedagogía de la Diversidad e Inclusión,William Santos Hinostroza
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,3.00 – 3.50,Tarde,Geografía Humana,Marcelino Erasmo Huamán Panés
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,3.00 – 3.50,Tarde,Museología y Didáctica de los bienes Culturales ,Pelayo Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,LUNES,6.20 – 7.10,Tarde/Noche,Sociología Política,Marcelino Erasmo Huamán Panéz
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Flaviano Zenteno Ruíz
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Ana María Navarro Porras
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,12.10 – 1.00,Mañana,Idiomas: Inglés Básico,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,8.00 – 8.50,Mañana,Arqueología Andina,Pelayo Teodóro Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,10.30 – 11.20,Mañana,Antropología Andina Amazónica,Marcelino Erasmo Huamán Panez
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,12.10 – 13.00,Mañana,Historia de América y el Mundo I,Eduardo Marino Pacheco Peña
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,3.00 – 3.50,Tarde,Identidad e Interculturalidad,Pelayo Teodoro Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre V,MARTES,4.40 – 5.30,Tarde,Perú Republicano,Eduardo Pacheco Peña
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,3.00 – 3.50,Tarde,Recursos Naturales del Perú,Ana Navarro Porras
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre VII,MARTES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,7.10 – 8.00,Mañana,Evaluación del Aprendizaje,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Betty Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría y Comunidad,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,8.00 – 8.50,Mañana,Ecología Dra Lucy Ricaldi Canchihuaman,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,10.30 – 11.20,Mañana,Psicología del Desarrollo Humano,Eva Elsa Condor Surichaqui
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,12.10 – 1.00,Mañana,Metodolos de Estudio de Trabajo Universitario,Contratado
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,8.00 – 8.50,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,10.30 – 11.20,Mañana,Sociología de la Educación,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,3.00 – 3.50,Tarde,Didáctica General Dra,Matos Atanacio
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre V,MIERCOLES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Sanyorei Porras Cosme
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,7.10 – 8.00,Mañana,Psicología del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,6.20 – 7.10,Tarde/Noche,Recursos Naturales del Perú,Ana Navarro Porras
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,3.00 – 3.50,Tarde,Museología y Didáctica de los bienes Culturales ,Pelayo Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre IX,MIERCOLES,4.40 – 5.30,Tarde,Sociología Política,Marcelino Erasmo Huamán Panéz
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,MIERCOLES,7.10 – 8.00,Mañana,Gastronomía,Sanyorei Porras Cosme
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,8.00 – 8.50,Mañana,Comunicación Oral y Escrita,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,9.40 – 10.30,Mañana,Realidad Nacional,Ana María Navarro Porras
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,11.20 – 12.10,Mañana,Matemática Básica,Flaviano Zenteno Ruíz
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,4.40 – 5.30,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,8.00 – 8.50,Mañana,Perú Prehispánico,Ana María Navarro Porrás
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre III,JUEVES,9.40 – 10.30,Mañana,Arqueología Andina,Pelayo Teodóro Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,12.10 – 13.00,Mañana,Antropología Andina Amazónica,Marcelino Erasmo Huamán Panez
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,3.00 – 3.50,Tarde,Identidad e Interculturalidad,Pelayo Teodoro Alvarez Llanos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre V,JUEVES,5.30 – 6.20,Tarde/Noche,Perú Republicano,Eduardo Pacheco Peña
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,3.00 – 3.50,Tarde,Calidad Educativa,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre VII,JUEVES,4.40 – 5.30,Tarde,Geografía Humana,Marcelino Erasmo Huamán Panés
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,JUEVES,3.00 – 3.50,Tarde,Tutoría y Comunidad,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Bety Ricaldi Canchihuamán
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,9.40 – 10.30,Mañana,Metodolos de Estudio de Trabajo Universitario,Contratado
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,11.20 – 12.10,Mañana,Comunicación Oral y Escrita,
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,8.00 – 8.50,Mañana,Filosofía de la Educación,William Santos
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,11.20 – 12.10,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,Semestre V,VIERNES,4.40 – 5.30,Tarde,Pedagogía de la Diversidad e Inclusión,William Santos Hinostroza
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,6.20 – 7.10,Tarde/Noche,Didáctica General Dra,Matos atanacio
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS HISTORIA CCSS Y TURISMO,,VIERNES,3.00 – 3.50,Tarde,Gastronomía,Samyuri Porras Cosme
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre I,LUNES,8.00 – 8.50,Mañana,Psicología del Desarrollo Humano,Eva Elsa Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,11.20 – 12.10,Mañana,Ecología Dra Lucy Ricaldi Canchihuaman,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,HORA,Desconocido,LUNES,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,8.00 – 8.50,Mañana,Filosofía Antigua Medieval,Javier De La Cruz Patiño
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre III,LUNES,9.40 – 10.30,Mañana,Epistemología de las Ciencias Sociales,Jacinto Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,11.20 – 12.10,Mañana,Problemas del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,3.00 – 3.50,Tarde,Psicología del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre V,LUNES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Sanyorei Porras Cosme
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,7.10 – 8.00,Mañana,Pedagogía de la Diversidad e Inclusión,William Santos Hinostroza
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,3.00 – 3.50,Tarde,Psicología Experimental,Eva Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre VII,LUNES,5.30 – 6.20,Tarde/Noche,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,3.00 – 3.50,Tarde,Lógica Dialéctica,Jacinto Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,LUNES,6.20 – 7.10,Tarde/Noche,Relaciones Humanas y Ciudadanía,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre I,MARTES,8.00 – 8.50,Mañana,Matemática Básica,Flaviano Zenteno Ruíz
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,10.30 – 11.20,Mañana,Realidad Nacional,Ana María Navarro Porras
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,12.10 – 1.00,Mañana,Idiomas: Inglés Básico,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,HORA,Desconocido,MARTES,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,8.00 – 8.50,Mañana,Paradígmas de la Psicología Educativa,Eva Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,10.30 – 11.20,Mañana,Epistemología de las Ciencias Sociales,Jacinto Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,3.00 – 3.50,Tarde,Psicología del Adoslescente,Alberto Cabrebra C.
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre V,MARTES,5.30 – 6.20,Tarde/Noche,Didáctica de la Filosofía y las Ciencias Sociales,Jacinto Alejandro Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,3.00 – 3.50,Tarde,Psicología Social Aplicada a la Educación,Javier De La Cruz Patiño
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre VII,MARTES,5.30 – 6.20,Tarde/Noche,Calidad Educativa,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,7.10 – 8.00,Mañana,Evaluación del Aprendizaje,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,3.00 – 3.50,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Betty Ricaldi Canchihuaman
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MARTES,5.30 – 6.20,Tarde/Noche,Tutoría y Comunidad,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre I,MIERCOLES,8.00 – 8.50,Mañana,Ecología Dra Lucy Ricaldi Canchihuaman,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,10.30 – 11.20,Mañana,Psicología del Desarrollo Humano,Eva Elsa Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,12.10 – 1.00,Mañana,Metodolos de Estudio de Trabajo Universitario,Contratado
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,HORA,Desconocido,MIERCOLES,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,8.00 – 8.50,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,10.30 – 11.20,Mañana,Sociología de la Educación,Oscar Sudario Remigio
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,3.00 – 3.50,Tarde,Didáctica General Dra,Matos Atanacio
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATiva,Semestre V,MIERCOLES,4.40 – 5.30,Tarde,Teoría y Diseño Curricular,Sanyorei Porras Cosme
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,7.10 – 8.00,Mañana,Psicología del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,3.00 – 3.50,Tarde,Estadística Aplicada a la Educación,Tito Rivera Espinoza
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre VII,MIERCOLES,5.30 – 6.20,Tarde/Noche,Psicología Experimental,Eva Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,3.00 – 3.50,Tarde,Relaciones Humanas y Ciudadanía,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,MIERCOLES,5.30 – 6.20,Tarde/Noche,Lógica Dialéctica,Jacinto Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre I,JUEVES,8.00 – 8.50,Mañana,Comunicación Oral y Escrita,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,9.40 – 10.30,Mañana,Realidad Nacional,Ana María Navarro Porras
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,11.20 – 12.10,Mañana,Matemática Básica,Flaviano Zenteno Ruíz
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,4.40 – 5.30,Tarde,Educación Física,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,HORA,Desconocido,JUEVES,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,8.00 – 8.50,Mañana,Problemas del Aprendizaje,Rudy Cuevas Cipriano
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre III,JUEVES,9.40 – 10.30,Mañana,Paradígmas de la Psicología Educativa,Eva Condor Surichaqui
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,12.10 – 13.00,Mañana,Filosofía Antigua Medieval,Javier De La Cruz Patiño
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,3.00 – 3.50,Tarde,Didáctica de la Filosofía y las Ciencias Sociales,Jacinto Alejandro Alejos López
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre V,JUEVES,5.30 – 6.20,Tarde/Noche,Psicología del Adoslescente,Alberto Cabrebra C.
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,3.00 – 3.50,Tarde,Calidad Educativa,Susy Santiago Lázaro
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre VII,JUEVES,5.30 – 6.20,Tarde/Noche,Psicología Social Aplicada a la Educación,Javier De La Cruz Patiño
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,3.00 – 3.50,Tarde,Tutoría y Comunidad,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre IX,JUEVES,4.40 – 5.30,Tarde,Proyectos de Innovación Educativa y Desarrollo Sustentable,Bety Ricaldi Canchihuaman
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,JUEVES,6.20 – 7.10,Tarde/Noche,Modelos de Evaluación Psicopedagógica,Luis Lombardi Palomino
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre I,VIERNES,8.00 – 8.50,Mañana,Idiomas: Inglés Básico,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,9.40 – 10.30,Mañana,Metodolos de Estudio de Trabajo Universitario,Contratado
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,11.20 – 12.10,Mañana,Comunicación Oral y Escrita,
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,HORA,Desconocido,VIERNES,Desconocido
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,8.00 – 8.50,Mañana,Filosofía de la Educación,William Santos
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,11.20 – 12.10,Mañana,Teoría de la educación,Orlando Campos Salvatierra
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,Semestre V,VIERNES,4.40 – 5.30,Tarde,Pedagogía de la Diversidad e Inclusión,William Santos Hinostroza
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,6.20 – 7.10,Tarde/Noche,Didáctica General Dra,Matos atanacio
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,3.00 – 3.50,Tarde,Evaluación del Aprendizaje,Antonio Yancán Camahualí
A    PROGRAMA DE ESTUDIOS  CCSS FILOSOFÍA Y PSICOLOGÍA EDUCATIVA,,VIERNES,3.00 – 3.50,Tarde,Modelos de Evaluación Psicopedagógica,Luis Lombardi Palomino
"""

class Command(BaseCommand):
    help = 'Puebla la base de datos con datos de prueba, incluyendo usuarios y horarios.'

    def parse_time(self, time_str):
        """Parsea la hora en formato 'H.MM' a un objeto time."""
        try:
            h, m = map(int, time_str.split('.'))
            # Corrección para casos como 1.00 -> 13:00
            if h < 7: h += 12
            return time(h, m)
        except:
            return None

    def clean_text(self, text):
        """Limpia y capitaliza el texto."""
        return text.strip().title()

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando la población del sistema ---'))

        # --- 1. Limpiar la base de datos ---
        self.stdout.write('... Limpiando datos existentes...')
        Curso.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Especialidad.objects.all().delete()
        Grupo.objects.all().delete()
        Carrera.objects.all().delete()
        Semestre.objects.all().delete()
        FranjaHoraria.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('-> Modelos principales limpiados.'))

        # --- 2. Crear usuarios clave ---
        self.stdout.write('... Creando usuarios clave...')
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', '12345', dni='00000001')

        User.objects.update_or_create(
            username='secretaria',
            defaults={
                'first_name': 'Secretaria', 'last_name': 'Académica', 'is_staff': True,
                'dni': '00000002', 'email': 'secretaria@example.com'
            }
        )
        User.objects.get(username='secretaria').set_password('123456')

        User.objects.update_or_create(
            username='director',
            defaults={
                'first_name': 'Director', 'last_name': 'General', 'is_staff': True,
                'dni': '00000003', 'email': 'director@example.com'
            }
        )
        User.objects.get(username='director').set_password('123456')
        self.stdout.write(self.style.SUCCESS('-> Usuarios admin, secretaria y director creados/actualizados.'))

        # --- 3. Crear Carrera y Semestre ---
        carrera_edu, _ = Carrera.objects.get_or_create(nombre="EDUCACION SECUNDARIA")
        semestre, _ = Semestre.objects.get_or_create(
            nombre=f'Semestre {date.today().year}-A',
            defaults={
                'fecha_inicio': date(date.today().year, 3, 1),
                'fecha_fin': date(date.today().year, 8, 31),
                'estado': 'ACTIVO', 'tipo': 'IMPAR'
            }
        )
        self.stdout.write(self.style.SUCCESS('-> Carrera y Semestre creados.'))

        # --- 4. Crear Franjas Horarias ---
        franjas_data = [
            ('MANANA', time(8, 0), time(8, 50)), ('MANANA', time(8, 50), time(9, 40)),
            ('MANANA', time(9, 40), time(10, 30)), ('MANANA', time(10, 30), time(11, 20)),
            ('MANANA', time(11, 20), time(12, 10)), ('MANANA', time(12, 10), time(13, 0)),
            ('TARDE', time(15, 0), time(15, 50)), ('TARDE', time(15, 50), time(16, 40)),
            ('TARDE', time(16, 40), time(17, 30)), ('TARDE', time(17, 30), time(18, 20)),
            ('TARDE', time(18, 20), time(19, 10)),
        ]
        for turno, inicio, fin in franjas_data:
            FranjaHoraria.objects.get_or_create(turno=turno, hora_inicio=inicio, hora_fin=fin)
        self.stdout.write(self.style.SUCCESS(f'-> {len(franjas_data)} Franjas Horarias creadas/verificadas.'))

        # --- 5. Procesar datos del horario ---
        self.stdout.write('... Procesando y poblando datos de horarios...')
        lines = SCHEDULE_DATA.strip().split('\n')[1:] # Omitir cabecera

        grupos_map = {}
        especialidades_map = {}
        docentes_map = {}

        semestre_map = {"Semestre I": 1, "Semestre III": 3, "Semestre V": 5, "Semestre VII": 7, "Semestre IX": 9}
        dias_map = {"LUNES": "Lunes", "MARTES": "Martes", "MIERCOLES": "Miércoles", "JUEVES": "Jueves", "VIERNES": "Viernes"}

        for i, line in enumerate(lines):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) != 7: continue

            programa_str, semestre_str, dia_str, hora_str, _, curso_str, docente_str = parts

            # Limpiar datos
            programa_str = re.sub(r'^A\s+PROGRAMA DE ESTUDIOS DE\s+', '', programa_str).title()
            programa_str = re.sub(r' Y ', ' y ', programa_str)

            if "Ccss" in programa_str:
                programa_str = "Ciencias Sociales, Filosofía y Psicología"
            if "Tecnología" in programa_str:
                programa_str = "Tecnología, Informática y Telecomunicaciones"
            if "Lenguas" in programa_str:
                programa_str = "Lenguas Extranjeras: Inglés y Francés"
            if "Historia" in programa_str:
                programa_str = "Historia, Ciencias Sociales y Turismo"

            curso_str = self.clean_text(curso_str)
            docente_str = self.clean_text(docente_str)
            dia = dias_map.get(dia_str)

            if not all([programa_str, curso_str, dia]): continue
            if "Desconocido" in curso_str: continue

            # Crear Grupo y Especialidad
            grupo_nombre = f"Grupo {programa_str.split(' ')[0]}"
            if grupo_nombre not in grupos_map:
                grupo, _ = Grupo.objects.get_or_create(nombre=grupo_nombre)
                grupos_map[grupo_nombre] = grupo
            grupo = grupos_map[grupo_nombre]

            if programa_str not in especialidades_map:
                especialidad, _ = Especialidad.objects.get_or_create(nombre=programa_str, defaults={'grupo': grupo})
                especialidades_map[programa_str] = especialidad
            especialidad = especialidades_map[programa_str]

            # Crear Docente
            docente = None
            if docente_str and "Desconocido" not in docente_str and "Contrato" not in docente_str:
                if docente_str not in docentes_map:
                    first_name = docente_str.split(' ')[0]
                    last_name = ' '.join(docente_str.split(' ')[1:])
                    username = f"{first_name[0].lower()}{last_name.split(' ')[0].lower() if last_name else ''}{random.randint(10,99)}"
                    docente_obj, created = Docente.objects.get_or_create(
                        dni=f"{random.randint(10000000, 99999999)}",
                        defaults={'first_name': first_name, 'last_name': last_name, 'username': username}
                    )
                    if created: docente_obj.set_password('123456')
                    docentes_map[docente_str] = docente_obj
                docente = docentes_map[docente_str]

            # Parsear Hora
            horas = [self.parse_time(t) for t in hora_str.replace(' ', '').split('–')]
            horario_inicio, horario_fin = (horas[0], horas[1]) if len(horas) == 2 and all(horas) else (None, None)

            # Crear Curso
            Curso.objects.create(
                nombre=curso_str,
                docente=docente,
                carrera=carrera_edu,
                especialidad=especialidad,
                semestre=semestre,
                semestre_cursado=semestre_map.get(semestre_str),
                dia=dia,
                horario_inicio=horario_inicio,
                horario_fin=horario_fin,
                duracion_bloques=random.choice([1, 2]) # Dato no provisto, se asigna aleatoriamente
            )

        self.stdout.write(self.style.SUCCESS(f'-> {len(lines)} líneas de horario procesadas.'))
        self.stdout.write(self.style.SUCCESS('--- ¡Población completa del sistema finalizada! ---'))