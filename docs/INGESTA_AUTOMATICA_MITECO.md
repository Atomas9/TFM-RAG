# Ingesta automática de partes de MITECO

## Objetivo

El repositorio descarga automáticamente el **Parte Definitivo de
Intervenciones (día previo)** publicado por MITECO. La automatización conserva
el PDF original y un manifiesto auditable, pero no ejecuta todavía el parser,
los embeddings ni la actualización de Chroma.

El código está aislado en
`src/miteco_rag/download_miteco_report.py` y no importa ni modifica los módulos
del RAG existentes.

## Flujo

```text
GitHub Actions, dos veces al día
        ↓
página oficial de actuaciones de MITECO
        ↓
descubrimiento del enlace "Parte Definitivo..."
        ↓
descarga y validación del PDF
        ↓
extracción de la fecha escrita en la primera página
        ↓
comprobación: fecha del parte = ayer en Europe/Madrid
        ↓
SHA-256 y control de duplicados/revisiones
        ↓
PDF + manifest.jsonl en data/raw/miteco
        ↓
commit automático solo si existen cambios
```

## Horarios

El workflow `.github/workflows/download-miteco-report.yml` se programa todos
los días a:

- 12:37, hora de `Europe/Madrid`;
- 18:17, hora de `Europe/Madrid`.

La segunda ejecución permite recuperar el documento si MITECO lo publica más
tarde de lo habitual o si la primera ejecución sufre un fallo temporal. El
workflow también admite ejecución manual desde la pestaña **Actions** de
GitHub mediante `workflow_dispatch`.

Los horarios programados de GitHub Actions no garantizan puntualidad exacta:
una ejecución puede comenzar con retraso. El descargador es idempotente, por lo
que ejecutar dos veces el mismo parte es seguro.

## Validaciones

Antes de escribir un archivo, el programa comprueba:

1. que la página de MITECO contiene el enlace esperado;
2. que la descarga responde correctamente;
3. que el contenido comienza con la firma `%PDF`;
4. que el tipo MIME, cuando se proporciona, corresponde a un PDF;
5. que PyMuPDF puede abrirlo;
6. que contiene el encabezado real de intervenciones del Ministerio;
7. que se puede extraer una fecha española de su primera página;
8. que esa fecha coincide con el día anterior en la zona horaria de Madrid.

Si MITECO mantiene temporalmente el parte de un día anterior, el workflow falla
de forma visible en lugar de archivar el documento con una fecha incorrecta.
La segunda ejecución del día vuelve a intentarlo.

## Nombres y revisiones

Los documentos nuevos usan el nombre:

```text
ActuacionesMITECO-definitivo-YYYY-MM-DD.pdf
```

Los PDF históricos que ya estaban en el proyecto pueden conservar sus nombres
anteriores. Si el descargador encuentra el mismo SHA-256 en uno de ellos, lo
registra en el manifiesto sin crear una copia.

Los estados posibles son:

- `downloaded`: parte nuevo guardado;
- `unchanged`: el mismo SHA-256 ya estaba registrado;
- `registered`: el contenido ya existía con un nombre histórico y se incorpora
  al manifiesto;
- `revised`: MITECO publicó una versión distinta para la misma fecha.

En una revisión se reemplaza el archivo de trabajo de esa fecha. La versión
anterior continúa recuperable en el historial de Git y el manifiesto conserva
su hash mediante `previous_sha256`.

## Manifiesto

`data/raw/miteco/manifest.jsonl` utiliza un objeto JSON por línea. Cada entrada
contiene:

- `report_date`: fecha indicada por el propio parte;
- `downloaded_at`: instante de descarga con zona horaria;
- `source_page_url`: página en la que se descubrió el enlace;
- `source_pdf_url`: URL descargada;
- `source_title`: texto del enlace;
- `sha256`: hash del contenido;
- `filename`: nombre almacenado;
- `content_length`: tamaño en bytes;
- `previous_sha256`: hash previo cuando se trata de una revisión.

El manifiesto facilita detectar duplicados, auditar el origen y reconstruir la
historia de revisiones.

## Ejecución local

Desde la raíz del repositorio y con el entorno activado:

```bash
conda activate RAG-TFM
python src/miteco_rag/download_miteco_report.py
```

Para probar una fecha concreta o un directorio temporal:

```bash
python src/miteco_rag/download_miteco_report.py \
  --expected-date 2026-07-24 \
  --output-dir /tmp/miteco-check
```

El argumento `--expected-date` es útil para pruebas manuales. La automatización
diaria no lo usa: calcula siempre el día anterior en `Europe/Madrid`.

## Commits automáticos

El workflow concede únicamente `contents: write`, configura la identidad
`github-actions[bot]` y añade solo `data/raw/miteco`. Si no hay diferencias
termina correctamente sin crear un commit.

Si la rama `main` exige pull requests o bloquea los pushes del bot, el paso de
publicación fallará. En ese caso será necesario permitir que GitHub Actions
escriba en la rama o cambiar en el futuro la estrategia de persistencia.

## Qué no hace todavía

Esta primera automatización solo garantiza la captura del documento original.
Quedan fuera deliberadamente:

- volver a ejecutar el parser al recibir un PDF;
- regenerar `fire_snapshots.jsonl`;
- calcular embeddings;
- actualizar ChromaDB;
- desplegar el índice resultante.

Estas tareas requieren decidir cómo conservar artefactos derivados y cómo
evitar que dos workflows modifiquen simultáneamente el corpus o el índice.
