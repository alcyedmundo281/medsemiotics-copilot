# Semilla de `AGENTS.md` para HolonMed

Copie el contenido siguiente —desde la línea horizontal— como `AGENTS.md` en la raíz del
repositorio de HolonMed, en su primer commit, antes de escribir cualquier funcionalidad. Está
redactado como contrato para cualquier agente o colaborador que trabaje ahí, y recoge lo aprendido
en `docs/arquitectura-agentica-transferible.md`.

Ajuste los apartados marcados con `<...>` antes de usarlo.

---

# HolonMed — contrato de ingeniería y seguridad

## Alcance y límites

HolonMed es <descripción en una frase de lo que el sistema afirma hacer>.

HolonMed **no emite diagnósticos ni indicaciones terapéuticas dirigidas al paciente**. Presenta
información y su procedencia para que un profesional la evalúe; la decisión clínica es siempre
humana. Cualquier cambio que acerque el sistema a emitir una conclusión directiva exige revisar
antes su clasificación regulatoria (ARCSA en Ecuador; los criterios de la FDA sobre apoyo a la
decisión clínica sirven de referencia sobre dónde está la línea).

## Reglas no negociables

1. **Nada de datos identificables en el repositorio.** Ni en el código, ni en los archivos de
   configuración, ni en los registros, ni en las descripciones de pull request, ni en los mensajes
   de commit. Sin nombres, cédulas, historias clínicas, imágenes ni fragmentos de expediente. Los
   casos de prueba son sintéticos.
2. **Nada de credenciales en el repositorio.** Ni tokens, ni claves, ni archivos OAuth, ni rutas
   locales de una máquina concreta. Todo llega por variable de entorno o gestor de secretos, y los
   errores nunca imprimen el valor de un secreto.
3. **Fallo cerrado.** Ante un dato ausente, una fuente que no resuelve o una configuración
   incompleta, el sistema se detiene y explica por qué. Nunca completa, aproxima ni infiere para
   poder continuar.
4. **Aprobación humana nombrada** antes de cualquier acción que salga del sistema: escribir en un
   expediente, enviar una notificación, publicar un resultado. La cadena que redacta no debe tener
   ruta hacia la ejecución.
5. **El determinismo vive en el código.** Esquemas, tablas de política y condiciones de rechazo se
   implementan y se prueban; no se confían a instrucciones en un prompt.

## Gates de calidad, desde el primer commit

Ninguna rama se fusiona sin que las cuatro pasen, en CI y en local:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Configure el CI en el primer commit, con el repositorio vacío. Es la única defensa que funciona
cuando nadie está mirando.

## Arquitectura obligatoria

- **Núcleo determinista**: funciones puras y tipadas, sin red y sin estado global, con pruebas.
  Es donde vive la lógica y donde se verifica.
- **Servicio en el borde**: envuelve el núcleo y aporta identidad, autorización, auditoría y
  persistencia. No reimplementa lógica. Es el único punto por donde se puede pasar.
- **El LLM habla con el servicio, nunca con los archivos.** Recibe un conjunto estrecho de
  operaciones tipadas; cada una se consulta contra una tabla de política que devuelve la decisión
  y su razón.
- **Auditoría append-only** de quién hizo y quién vio qué, con marca de tiempo. Incluye lecturas.
- **Canal de razonamiento separado del canal de acción.** El texto libre de un expediente es
  entrada no confiable: una frase dentro de una nota puede leerse como instrucción. Ese contenido
  nunca alcanza un contexto capaz de ejecutar acciones.
- **Sustrato compartido neutral**: el índice de fuentes y la capa de conocimiento no conocen a sus
  consumidores, para que sirvan igual a la clínica y a la docencia.

## Cómo se trabaja

- Se desarrolla en una rama, nunca directo sobre `main`.
- Cada pull request explica por qué existe el cambio, no solo qué cambió, y espera CI en verde.
- Un cambio que toca política, auditoría o manejo de datos de paciente se revisa aunque sea
  pequeño.

## Qué hacer ante la duda

Si falta información para completar una tarea correctamente, pregunte o deténgase. No invente un
valor por defecto razonable, no complete un dato clínico ausente, no asuma una identidad de
usuario. En este dominio, una respuesta segura y equivocada cuesta más que ninguna respuesta.
