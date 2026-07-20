# Revisión de la fase 1

Fecha de revisión: 2026-07-20.

Archivo revisado: `src/miteco_rag/parseo_y_chuncking.py`.

Se ha comprobado la sintaxis, se ha procesado el corpus completo y se han
validado los artefactos generados. El módulo ya no ejecuta demostraciones ni
escribe archivos durante su importación.

## Estado alcanzado

El parser ya no se limita a leer y normalizar el PDF. La implementación actual
incluye:

- lectura de texto por páginas con PyMuPDF;
- conservación del texto original, limpio y normalizado en `PDFLine`;
- hash SHA-256 y metadatos comunes del documento;
- catálogos de comunidades autónomas, provincias, alias y países extranjeros;
- una máquina de estados que conserva la geografía vigente;
- separación de incendios en objetos `FireBlock`;
- exclusión del resumen estadístico situado al final del parte;
- extracción de la localización;
- extracción del estado del incendio y de la situación operativa (`S.O.`);
- extracción de notas y, cuando consta el año, de la fecha de inicio;
- extracción de medios asignados mediante el modelo `AssignedResource`;
- obtención de una lista sin duplicados de códigos de medios;
- construcción de un `FireSnapshot` validado por Pydantic;
- generación determinista de `snapshot_id` e `incident_key`;
- construcción de `raw_text` y `chunk_text` para cada snapshot;
- versionado de la salida mediante `parser_version`;
- orquestación completa de un PDF mediante `parse_miteco_pdf()`;
- procesamiento determinista del corpus mediante `parse_pdf_directory()`.
- validación agregada mediante `validate_snapshots()`;
- informe de ejecución validado como `ParserReport`;
- exportación de un snapshot por línea en `fire_snapshots.jsonl`;
- exportación del informe en `parser_report.json`;
- orquestación completa mediante `run_phase1()` y una entrada `main()`
  protegida con `if __name__ == "__main__"`.

La estructura elegida es adecuada para esta fase: primero se delimitan los
bloques y después cada función interpreta un campo concreto. Esto facilita
probar y corregir cada extractor de forma independiente.

## Resultado de las comprobaciones

### Comprobaciones superadas

- `python -m py_compile` no detecta errores de sintaxis.
- La muestra incluida en el archivo procesa el primer PDF.
- En ese documento se obtienen 9 bloques y los tres primeros devuelven
  localización, estado, situación operativa, nota y códigos de medios.
- Las fechas principales y las últimas actualizaciones se extraen de los ocho
  documentos.
- El recorrido completo finaliza sin errores sobre los ocho PDF.
- La máquina de estados delimita 48 bloques: 47 de España y uno de Portugal.
- Se construyen 48 objetos `FireSnapshot` con 48 `snapshot_id` únicos.
- Los 48 bloques contienen un estado reconocible.
- Ningún `chunk_text` está vacío y ningún snapshot tiene un rango de páginas
  invertido.
- Se obtienen 37 valores distintos de `incident_key`; siete claves agrupan
  observaciones repetidas de una misma ubicación.
- `parse_pdf_directory()` devuelve los mismos 48 snapshots en ejecuciones
  consecutivas y conserva los 8 documentos.
- Una carpeta sin PDF genera `FileNotFoundError` con la ruta inspeccionada.
- Un PDF inexistente genera `FileNotFoundError` antes de intentar abrirlo.
- Importar el módulo no procesa PDF ni escribe archivos.
- El JSONL contiene 48 líneas JSON válidas y reconstruibles como
  `FireSnapshot`.
- Los 48 registros serializados mantienen identificadores únicos y texto UTF-8.
- El informe se reconstruye correctamente como `ParserReport`, contiene los 8
  documentos, 47 snapshots españoles, uno extranjero y cero errores.
- `fire_snapshots.jsonl` y `parser_report.json` están excluidos de Git.

### Error detectado y corregido

El modelo `PDFLine` define el atributo `cleaned_text`, pero hay dos accesos a un
atributo inexistente llamado `clean_text`:

1. En la rama que reconoce un país extranjero:

   ```python
   current_province = line.clean_text
   ```

2. Al unir las líneas que continúan una nota:

   ```python
   line.clean_text
   ```

Ambos accesos se corrigieron para usar `line.cleaned_text`. Antes de la
corrección, el primer caso hacía que la ejecución terminara con `AttributeError`
al alcanzar Portugal; el segundo podía fallar cuando una nota tuviera contenido
en líneas posteriores.

La prueba del final del archivo no descubría el problema porque solo muestra
los tres primeros bloques del primer PDF. El recorrido completo posterior a la
corrección confirma que el error ha quedado resuelto.

## Resultados del corpus actual

Los recuentos siguientes se obtuvieron con el parser corregido:

| Documento | Fecha obtenida del contenido | Líneas | Bloques | No españoles |
| --- | --- | ---: | ---: | ---: |
| `ActuacionesMITECO-definitivo.pdf` | 2026-07-05 | 161 | 9 | 1 |
| `ActuacionesMITECO-definitivo-12072026.pdf` | 2026-07-12 | 154 | 9 | 0 |
| `ActuacionesMITECO-definitivo13072026.pdf` | 2026-07-13 | 156 | 10 | 0 |
| `ActuacionesMITECO-definitivo14072026.pdf` | 2026-07-14 | 121 | 6 | 0 |
| `ActuacionesMITECO-definitivo15072025.pdf` | 2026-07-15 | 122 | 5 | 0 |
| `ActuacionesMITECO-definitivo17072026.pdf` | 2026-07-17 | 127 | 4 | 0 |
| `ActuacionesMITECO-definitivo18072026.pdf` | 2026-07-18 | 121 | 3 | 0 |
| `ActuacionesMITECO-definitivo19072026.pdf` | 2026-07-19 | 111 | 2 | 0 |
| **Total** |  | **1073** | **48** | **1** |

El archivo `ActuacionesMITECO-definitivo15072025.pdf` contiene un parte fechado
el 15 de julio de 2026. El año `2025` del nombre parece una errata del nombre
local. Para los metadatos se debe mantener como autoridad la fecha extraída del
contenido, conservando también `source_file` para trazabilidad.

## Aspectos que todavía requieren validación

### Medios asignados

El extractor produce 157 objetos `AssignedResource` en los ocho documentos,
pero esta cifra aún no es una prueba de exactitud. Falta
comparar cada salida con las líneas originales para comprobar:

- que no se incorporan encabezados como continuación del medio anterior;
- que `RESOURCE_PATTERN` reconoce todos los formatos de código;
- que cantidad, código y descripción se separan correctamente;
- cómo extraer `origin`, que actualmente siempre queda en `None`.

### Notas y fechas de inicio

Se detectan 29 bloques con nota y 4 fechas de inicio con año completo. Deben
añadirse pruebas para notas partidas entre páginas y fechas sin año. El parser
hace bien en no inventar el año cuando el documento no lo contiene.

### Estados

Los 48 bloques actuales contienen un estado reconocido. Aun así, el patrón
solo acepta un estado formado por una palabra. Conviene conservar una prueba
con cada valor real encontrado y otra con un estado desconocido.

### Identidad de incendios

`snapshot_id` funciona como identificador técnico de la observación: los 48
valores son únicos y reproducibles para los PDF actuales.

`incident_key` debe considerarse una clave heurística de agrupación. Cuando no
hay fecha de inicio, agrupa por país, comunidad, provincia y localización. Este
comportamiento reúne siete series de ubicaciones repetidas en el corpus, como
`CASO`, `ORÉS` y `MIERLA, LA`.

La clave no demuestra por sí sola que se trate del mismo incendio. Puede unir
dos episodios diferentes de una misma ubicación si ambos carecen de fecha de
inicio. También puede separar un episodio cuando la fecha solo aparece en uno
de los partes. Esto sucede con `VILLABLINO`: el snapshot del 12 de julio incluye
la fecha de inicio 2026-07-07, mientras los del 13 y 14 no la contienen.

Por ello, `incident_key` no se utilizará para deduplicar snapshots. La
resolución definitiva de episodios queda como una transformación posterior que
trabajará sobre el corpus ordenado cronológicamente.

## Mejoras pendientes

1. Añadir pruebas pytest reales; `tests/` todavía solo contiene su README.
2. Tipar el retorno de `extract_pdf_lines()` como `list[PDFLine]` y su lista
   interna.
3. Decidir cómo representar la zona horaria local de `last_update`; el instante
   de generación del informe ya se almacena en UTC.
4. Añadir una fase posterior de resolución temporal para convertir las claves
   heurísticas en episodios confirmados o marcados como ambiguos.
5. Corregir finalmente `chuncking` a `chunking` cuando el módulo deje de ser un
   archivo de aprendizaje y se convierta en una interfaz estable.

## Siguiente incremento recomendado

La salida estructurada ya permite comenzar la siguiente fase:

1. cargar y validar `fire_snapshots.jsonl`;
2. seleccionar los 47 snapshots de España;
3. generar embeddings normalizados de `chunk_text` con `BAAI/bge-m3`;
4. convertir los metadatos a valores planos compatibles con ChromaDB;
5. reconstruir una colección persistente usando `snapshot_id` como ID;
6. comprobar recuperación semántica, filtros exactos y consultas combinadas.

La revisión manual de medios y notas y la creación de pruebas pytest continúan
como trabajo de calidad paralelo, pero no bloquean el primer prototipo del
índice vectorial.
