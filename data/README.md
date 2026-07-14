# Datos del proyecto

Esta carpeta contiene datos locales y artefactos regenerables. Su contenido no
se versiona, salvo este documento y los archivos `.gitkeep`.

## Directorios

- `raw/miteco/`: PDF originales descargados de MITECO.
- `processed/`: snapshots parseados, informes de validacion y JSONL.
- `chroma/`: persistencia local de ChromaDB.

Los PDF deben conservar su nombre original y asociarse a su URL, hash SHA-256 y
fecha de descarga en el manifiesto de ingesta que se implementara mas adelante.

No deben guardarse claves de API, tokens ni datos privados en esta carpeta.

