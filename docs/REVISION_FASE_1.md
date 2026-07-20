# Revisión de la fase 1

Fecha de revisión: 2026-07-20.

Archivo revisado: `src/miteco_rag/parseo_y_chuncking.py`.

Se ha comprobado la sintaxis, se ha ejecutado la muestra incluida al final del
archivo y se ha procesado el corpus completo. Durante la revisión se corrigieron
dos accesos a `clean_text`, ya que el atributo definido por `PDFLine` se llama
`cleaned_text`.

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

1. Mover la demostración del final a una función `main()` y protegerla con
   `if __name__ == "__main__"`; ahora importar el módulo procesa un PDF e
   imprime resultados.
2. Comprobar que existen PDF antes de acceder a `all_pdf[0]`.
3. Añadir pruebas pytest reales; `tests/` todavía solo contiene su README.
4. Tipar el retorno de `extract_pdf_lines()` como `list[PDFLine]` y su lista
   interna.
5. Decidir cómo representar la zona horaria de `last_update`; `timezone` sigue
   importado sin utilizarse.
6. Añadir una fase posterior de resolución temporal para convertir las claves
   heurísticas en episodios confirmados o marcados como ambiguos.
7. Validar y exportar los `FireSnapshot` a JSONL antes de generar embeddings.
8. Corregir finalmente `chuncking` a `chunking` cuando el módulo deje de ser un
   archivo de aprendizaje y se convierta en una interfaz estable.

## Siguiente incremento recomendado

El siguiente paso no debería ser ChromaDB todavía. Primero conviene:

1. crear pruebas para los recuentos de los ocho PDF y para Portugal;
2. inspeccionar manualmente una muestra de medios y notas;
3. probar la estabilidad y las limitaciones conocidas de ambos identificadores;
4. implementar la validación agregada del corpus;
5. exportar y validar un JSONL reproducible.

Cuando esos pasos sean estables, cada registro del JSONL podrá convertirse en
un chunk y enriquecerse con su embedding.
