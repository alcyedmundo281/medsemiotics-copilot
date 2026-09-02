# Arquitectura agéntica transferible

Este documento recoge lo que MedSemiotics Copilot demostró en su primer semestre de uso real y que
puede trasladarse a otros sistemas del ecosistema —medsemiotics-db, HolonMed— o a la cátedra de
cualquier otro profesor. Está escrito para que sirva de punto de partida sin necesidad de leer el
código ni de haber participado en su construcción.

Distingue tres cosas: los principios que sí transfieren, las advertencias sobre lo que no se
hereda, y la evidencia concreta de por qué cada principio está aquí.

---

## 1. El determinismo vive en el código, no en el prompt

Un agente que se autorregula por instrucciones es una promesa. Un agente que choca contra una
validación es una garantía. Todo lo que deba cumplirse siempre —el esquema de los datos, la tabla
de permisos, las condiciones de rechazo— tiene que estar en código que el modelo no pueda
reescribir en tiempo de ejecución.

En este repositorio eso son los modelos Pydantic congelados con `extra="forbid"`, las excepciones
de dominio, y una suite de pruebas mayor que el propio código: 14.445 líneas de pruebas frente a
13.106 de fuente.

## 2. Fallo cerrado: negarse antes que inventar

Cuando falta un dato, el sistema se detiene y lo dice. No completa, no aproxima, no infiere.

- Sin guía curada para un tema, el Teaching Coach se niega a redactar el brief.
- Sin token configurado, el backend responde 503 en lugar de aceptar un valor por defecto.
- Sin fuente que resuelva, un contenido no debería servirse como verificado.

Esta regla es la que hace que el sistema sea utilizable en un contexto profesional. Su valor no
está en lo que produce, sino en lo que se niega a producir.

## 3. La política es una tabla explícita por operación

Los permisos no se deciden en el razonamiento del agente: se consultan. `ClassroomAccessPolicy`
declara operación por operación qué está permitido, y cada decisión devuelve además la razón por
la que se tomó. Un permiso que no puede explicarse no es un permiso auditable.

## 4. Una sola fuente de verdad, y todo lo demás derivado

El sílabo oficial manda; el horario, el plan de temas y la bitácora se generan de él con
`scripts/sync_syllabus_v2_to_config.py`, y una prueba falla si alguien edita a mano un archivo
generado. Dos registros del mismo hecho terminan siempre por contradecirse; la única defensa es
que uno sea derivado del otro y que la derivación esté verificada.

## 5. El sustrato compartido no pertenece a ningún consumidor

Las capas transversales —el índice de fuentes validadas, la espina dorsal de competencias— no
deben conocer a sus consumidores. Si el índice de fuentes tiene campos como "semana" o "tema del
sílabo", queda hipotecado a la capa educativa y no servirá para la clínica. Educación y clínica
son dos consumidores distintos de un mismo sustrato, cada uno con su vocabulario.

## 6. El estado vive en archivos versionados: el sistema sobrevive a la IA

El registro docente es texto plano bajo control de versiones. Si mañana desaparece el asistente,
la enseñanza sigue en pie y el histórico permanece legible y auditable. Esta propiedad es la que
convence a un colega escéptico, y es más valiosa que cualquier capacidad del modelo.

## 7. Aprobación humana nombrada antes de toda acción externa

Nada se publica solo. Los publicadores construyen un borrador revisable y declaran que no
publicaron nada. La cadena que redacta no tiene ruta hacia la publicación: es una propiedad de la
arquitectura, no una promesa de comportamiento.

## 8. Núcleo determinista con CLI; servicio solo en el borde

Para un usuario y una máquina, un comando —`uv run <script>`— es superior a un servidor: sin
puerto, sin autenticación que administrar, sin despliegue, y con un código de salida que permite
detener la cadena. Es también más fácil de restringir para un LLM, porque cada invocación es una
acción acotada.

El servicio se justifica cuando aparece **el segundo usuario o el primer dato de paciente**, y
entonces no reimplementa la lógica: envuelve el mismo núcleo y aporta lo que el núcleo no puede
dar solo —identidad, autorización, auditoría y persistencia—. El LLM habla con el servicio, nunca
con los archivos, y recibe un conjunto estrecho de operaciones tipadas en lugar de un sistema de
archivos.

## 9. Separar el canal de razonamiento del canal de acción

El texto libre es entrada no confiable. Una instrucción incrustada en una nota clínica, en un
comentario de estudiante o en un documento externo puede leerse como orden. Ningún contenido de
esa procedencia debe alcanzar un contexto capaz de ejecutar acciones.

---

## Advertencias: lo que no se hereda

**"No es un dispositivo médico" no se hereda.** MedSemiotics Copilot lo tiene ganado porque no
maneja datos de pacientes, sus casos son sintéticos y su salida va a un aula. HolonMed cambia los
tres supuestos a la vez. La clasificación regulatoria depende de qué afirme hacer el sistema, y
conviene resolverla en el diseño —con ARCSA en Ecuador, y mirando los criterios de la FDA sobre
apoyo a la decisión clínica como el mejor mapa público de dónde está la línea.

**El calendario del autor no es el método.** Este sistema nació de una práctica concreta y arrastra
sus supuestos: el día de clase se deriva del día de la fecha de inicio, o sea que asume una sola
sesión semanal; la bitácora registra un tema por sesión; el avance es lineal; y la clave del
esquema se llama `schedule_18_weeks`. Ante cada estructura, la pregunta al escalar es: ¿esto es un
principio, o es cómo doy clases yo? El fallo cerrado es principio. Dieciocho semanas no lo es.

**El contenido docente actual no está anclado a fuentes.** Las guías de las semanas 11 a 18 fueron
redactadas desde conocimiento clínico estándar y ninguna afirmación lleva PMID. Sirven como
andamiaje de aula; no como contenido final de un sistema que presuma de anclaje verificado. El
puente con medsemiotics-db es lo que cambia eso, y hasta entonces conviene que el sistema declare
qué está verificado y qué no, en vez de servirlo todo por igual.

**La adopción es por profesor, no por institución.** Los cambios que movieron la educación médica
empezaron en cátedras sueltas y no en planes estratégicos. Para un decano, además, el argumento
más fuerte no es la IA sino la trazabilidad curricular que las acreditaciones ya exigen y que hoy
se produce como papeleo retrospectivo.

---

## Evidencia: por qué las pruebas y el CI van primero

Durante el desarrollo de este repositorio, tres regresiones llegaron a la rama principal y ninguna
fue detectada por revisión humana ni por el criterio del agente:

| Regresión | Consecuencia | Qué la detectó |
|---|---|---|
| El backend pasó a aceptar un token por defecto conocido cuando no había secreto configurado | Cualquiera que conociera ese valor podía leer la superficie | Revisión del diff contra la prueba de fallo cerrado |
| Rutas absolutas y correo de trabajo escritos en un repositorio público | Datos personales expuestos; el script solo funcionaba en una máquina | Auditoría del árbol |
| Un script preparaba material solo para la semana 11, con el texto incrustado | Habría dejado de funcionar la semana siguiente | 53 errores de lint que dejaron el CI en rojo |

La conclusión práctica es que los gates —`ruff check`, `ruff format --check`, `mypy`, `pytest`—
deben existir desde el primer commit, con el repositorio todavía vacío. Aquí llegaron después, y
hubo días con la rama principal en rojo sin que nadie lo advirtiera. En un proyecto clínico eso no
se corrige retroactivamente.
