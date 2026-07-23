# Proceso de desarrollo del RAG de incendios de MITECO

Este documento explica de forma resumida y ordenada cómo se ha construido el
proyecto. Está pensado para entender el recorrido completo sin tener que leer
la bitácora diaria ni revisar todos los commits.

La bitácora responde a «¿qué se hizo cada día?». Este documento responde a
«¿cómo funciona el proyecto, por qué se tomaron estas decisiones y cómo hemos
llegado hasta aquí?».

## 1. Objetivo del proyecto

El objetivo es crear un sistema RAG capaz de responder preguntas sobre los
partes diarios de actuaciones en incendios forestales publicados por MITECO.

El sistema debe permitir dos tipos de búsqueda:

- búsqueda semántica, para encontrar incendios relacionados con el significado
  de una pregunta;
- búsqueda por metadatos, para aplicar condiciones exactas como provincia,
  comunidad autónoma, localización, estado o fecha.

El flujo general construido hasta ahora es:

```text
PDF de MITECO
      ↓
extracción y limpieza del texto
      ↓
separación de cada incendio
      ↓
FireSnapshot + chunk_text + metadatos
      ↓
fire_snapshots.jsonl
      ↓
embeddings BGE-M3
      ↓
colección persistente de ChromaDB
      ↓
búsqueda semántica + filtros de metadatos
```

La generación de la respuesta final mediante un LLM es la siguiente fase del
proyecto.

## 2. Preparación del repositorio y del entorno

El proyecto se reorganizó para separar el código nuevo del material anterior.
Los documentos y programas utilizados como referencia se conservaron en
`extras`, mientras que la implementación principal se situó en
`src/miteco_rag`.

Se creó el entorno Conda `RAG-TFM` con Python 3.11. Las versiones de NumPy,
PyTorch y Transformers tuvieron que ajustarse para mantener compatibilidad con
el Mac Intel utilizado durante el desarrollo.

Los PDF originales, los JSONL procesados y el índice de Chroma no se incluyen
en Git. Son datos locales y regenerables. El repositorio solo conserva el
código, las pruebas y la documentación necesarios para reconstruirlos.

## 3. Lectura de los PDF

Los partes de MITECO son PDF con una estructura visual pensada para personas,
no para su tratamiento automático. El primer paso fue extraer su texto con
PyMuPDF:

```python
document = pymupdf.open(pdf_path)
```

La extracción conserva el número de página de cada línea. Esto es importante
porque cada respuesta del RAG debe poder indicar de qué documento y página
procede la información.

Después se limpian espacios y caracteres problemáticos y se crea una versión
normalizada para reconocer encabezados y campos sin depender de mayúsculas o
tildes. Se conservan por separado:

- el texto original, útil para trazabilidad;
- el texto limpio, utilizado por el parser;
- el texto normalizado, utilizado para comparar patrones.

## 4. Separación de cada incendio

Un PDF contiene varios incendios. No era adecuado guardar una página o un PDF
completo como un único chunk, porque una búsqueda podría mezclar provincias,
estados y medios de incendios distintos.

La unidad documental elegida es un **snapshot**: el estado de un incendio tal
como aparece en un parte concreto.

El parser recorre las líneas y mantiene el contexto geográfico. Esto es
necesario porque los partes no siempre repiten la comunidad autónoma o la
provincia delante de cada incendio. Cuando aparece una nueva localización se
abre un bloque y se reúnen sus datos hasta encontrar el siguiente incendio.

De cada bloque se extraen, entre otros:

- país;
- comunidad autónoma;
- provincia;
- localización;
- estado;
- situación operativa;
- medios asignados;
- nota;
- posible fecha de inicio;
- fecha del parte;
- archivo y páginas de origen.

El corpus local utilizado durante esta fase contiene ocho PDF y produce 48
snapshots: 47 de España y uno de Portugal. El registro portugués se conserva
en el índice y puede incluirse o excluirse mediante el metadato `country`.

## 5. Validación con Pydantic

Cada incendio se representa mediante el modelo Pydantic `FireSnapshot`.
Pydantic comprueba que los datos tengan la estructura y los tipos esperados
antes de exportarlos.

Por ejemplo, una fecha debe ser una fecha válida, los medios deben respetar su
modelo y los campos obligatorios no pueden desaparecer silenciosamente.

Se utilizan dos identificadores diferentes:

- `snapshot_id`: identifica de forma única un incendio dentro de un parte;
- `incident_key`: intenta relacionar snapshots que podrían corresponder al
  mismo incendio en días diferentes.

`incident_key` es todavía heurístico. Utiliza geografía, localización y fecha
de inicio cuando está disponible. Si MITECO omite esa fecha, dos episodios
distintos en la misma ubicación podrían quedar agrupados o un mismo episodio
podría dividirse.

## 6. Construcción del chunk

El embedding no se calcula directamente sobre las líneas originales. Para cada
snapshot se construye un `chunk_text` autosuficiente y legible:

```text
Fecha del parte: 2026-07-13
País: ES
Comunidad autónoma: Castilla y León
Provincia: León
Localización: VILLABLINO
Estado: ACTIVO
...
Fuente: ActuacionesMITECO..., página 2
```

Incluir los campos principales dentro del texto ayuda a la búsqueda semántica
y permite enviar el chunk directamente al futuro LLM generador. Los mismos
valores se guardan también como metadatos planos para realizar filtros exactos.

## 7. Exportación de la fase de parseo

Al ejecutar:

```bash
python src/miteco_rag/parseo_y_chuncking.py
```

se vuelven a procesar todos los PDF y se generan dos archivos:

### `fire_snapshots.jsonl`

Contiene un `FireSnapshot` por línea. Es la entrada utilizada para construir el
índice vectorial.

### `parser_report.json`

Contiene información sobre la ejecución del parser: documentos procesados,
recuentos, advertencias y errores. Sirve para diagnosticar el pipeline sin
tener que inspeccionar todo el JSONL.

La implementación actual no es incremental: si se añaden nuevos PDF, vuelve a
procesar la carpeta completa y reemplaza las salidas.

## 8. Embeddings y almacenamiento en ChromaDB

El script:

```bash
python src/miteco_rag/embeddings_chroma.py
```

realiza tres operaciones:

1. carga y valida cada línea de `fire_snapshots.jsonl`;
2. convierte cada `chunk_text` en un embedding normalizado con `BAAI/bge-m3`;
3. almacena ID, documento, embedding y metadatos en ChromaDB.

La colección persistente se llama:

```text
MITECO_fire_snapshots
```

Los datos se almacenan localmente en `data/chroma`. Se utiliza `upsert`, por lo
que una nueva ejecución inserta registros desconocidos y actualiza los que ya
comparten ID. No elimina automáticamente registros antiguos que hayan
desaparecido del JSONL.

## 9. Primera búsqueda semántica

La consulta del usuario se convierte en un embedding utilizando el mismo
modelo BGE-M3. Chroma compara ese vector con los documentos almacenados y
devuelve los `top_k` más próximos.

La búsqueda semántica funciona bien para conceptos generales, pero no garantiza
que una palabra como `León` se interprete como una provincia. También puede
recuperar un incendio de otra provincia porque alguno de sus medios procede de
una base situada en León.

Esta observación llevó a añadir filtros exactos de metadatos.

## 10. Búsqueda híbrida y filtros deterministas

El módulo `query_filters.py` interpreta condiciones presentes en la pregunta y
construye el argumento `where` de Chroma.

Actualmente reconoce:

- países, comunidades, provincias y localizaciones conocidas;
- estados y situaciones operativas;
- inclusiones y exclusiones;
- coordinaciones como `León o Palencia`;
- contrastes como `no de León, sino de Palencia`;
- fechas exactas, intervalos, meses y años;
- expresiones de presente e históricas.

Cuando se solicitan varias provincias:

```text
Incendios en León y Palencia
```

el filtro utiliza `$in`, que equivale a León **o** Palencia:

```python
{
    "province_normalized": {
        "$in": ["leon", "palencia"]
    }
}
```

Las condiciones de campos distintos sí se combinan mediante `$and`. Por
ejemplo, `activos en León` exige simultáneamente provincia León y estado
`ACTIVO`.

## 11. Interpretación temporal

El catálogo de metadatos conoce las fechas disponibles y calcula
`latest_report_date`.

Se acordaron las siguientes reglas:

- `¿Qué incendios están activos?` utiliza el último parte disponible;
- `¿Qué incendios hay?` utiliza todos los registros del último parte,
  independientemente de su estado;
- `¿Qué incendios estuvieron activos?` es una consulta histórica;
- `¿Qué incendios estaban activos el 13 de julio?` utiliza esa fecha;
- `¿Qué incendios estuvieron activos en julio?` utiliza todo el mes.

Las palabras `hay`, `existen`, `actualmente`, `ahora`, `hoy`, `a día de hoy`,
`en este momento` y `último parte` se consideran expresiones de presente cuando
no existe una fecha explícita.

El último parte significa la fecha máxima del corpus. No equivale a información
en tiempo real, por lo que la respuesta final deberá indicar siempre la fecha
de referencia.

## 12. Estado actual

En este momento están completadas:

- lectura y limpieza de PDF;
- separación de incendios;
- extracción de metadatos;
- validación de snapshots;
- exportación JSONL e informe del parser;
- generación de embeddings;
- almacenamiento persistente en Chroma;
- búsqueda semántica;
- búsqueda híbrida con filtros deterministas;
- pruebas automatizadas del parser de consultas y del retrieval.

La suite actual contiene 38 pruebas y puede ejecutarse con:

```bash
python -m pytest -q
```

## 13. Límites conocidos

La versión actual todavía tiene varios límites:

- el parser lingüístico determinista solo entiende las construcciones que se
  han programado;
- las localizaciones exactas proceden del corpus y no de un catálogo completo
  de municipios;
- `top_k` puede devolver resultados de una sola provincia aunque se hayan
  solicitado varias;
- una búsqueda sin resultados no siempre significa que un incendio no
  existiera, sino que no consta en los partes disponibles;
- todavía no se ha calibrado un umbral de distancia semántica;
- no existe generación de respuesta ni memoria conversacional;
- la identidad entre snapshots de días distintos sigue siendo heurística.

## 14. Siguiente fase: interpretación con LLM

La siguiente etapa incorporará un LLM para interpretar preguntas que superen
las reglas deterministas.

El LLM no escribirá directamente el `where` de Chroma. Devolverá una intención
estructurada que será:

1. validada con Pydantic;
2. normalizada con los catálogos del proyecto;
3. comprobada para detectar contradicciones;
4. traducida al filtro final mediante código determinista.

Durante el desarrollo se compararán en paralelo:

```text
pregunta
   ├── parser determinista
   └── parser mediante LLM
```

Esto permitirá medir cuándo mejora el LLM y cuándo introduce errores.

Después se podrá construir un workflow con LangGraph que incluya:

- clasificación de preguntas relacionadas o no con incendios;
- selección del plan de retrieval;
- consulta a Chroma;
- evaluación de la suficiencia del contexto;
- un único intento controlado de reformulación;
- generación de una respuesta fundamentada.

Antes de montar el grafo completo se implementará el parser LLM como una
función independiente y comprobable.

## 15. Archivos principales

| Archivo | Responsabilidad |
| --- | --- |
| `src/miteco_rag/parseo_y_chuncking.py` | Lectura, parseo, snapshots y JSONL |
| `src/miteco_rag/embeddings_chroma.py` | Embeddings e indexación |
| `src/miteco_rag/query_filters.py` | Interpretación determinista de filtros |
| `src/miteco_rag/retrieval_chroma.py` | Implementación de retrieval desarrollada durante el aprendizaje |
| `src/miteco_rag/retrieval_chroma_solution.py` | Implementación de referencia |
| `tests/` | Pruebas automatizadas |
| `CUADERNO_DE_BITACORA.md` | Registro diario detallado |
| `docs/ARQUITECTURA.md` | Decisiones técnicas de arquitectura |

## 16. Cómo reconstruir el flujo actual

Con el entorno `RAG-TFM` activado y los PDF en `data/raw/miteco`:

```bash
python src/miteco_rag/parseo_y_chuncking.py
python src/miteco_rag/embeddings_chroma.py
python src/miteco_rag/retrieval_chroma.py
```

Para validar el proyecto:

```bash
python -m pytest -q
```

