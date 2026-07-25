# Datos del proyecto

Esta carpeta contiene documentos fuente y artefactos regenerables. Los partes
originales de MITECO se versionan para disponer de un corpus histórico; los
datos procesados y el índice vectorial continúan siendo locales.

## Directorios

- `raw/miteco/`: PDF originales descargados de MITECO y `manifest.jsonl`,
  versionados en Git.
- `processed/`: snapshots parseados, informes de validacion y JSONL.
- `chroma/`: persistencia local de ChromaDB.

El descargador automático asigna a los nuevos PDF el patrón
`ActuacionesMITECO-definitivo-YYYY-MM-DD.pdf`. Los nombres históricos se
conservan para no romper las referencias existentes. Cada descarga se asocia a
su URL, hash SHA-256, fecha del parte y fecha de descarga en
`raw/miteco/manifest.jsonl`.

La automatización y las reglas de revisión se explican en
[`docs/INGESTA_AUTOMATICA_MITECO.md`](../docs/INGESTA_AUTOMATICA_MITECO.md).

No deben guardarse claves de API, tokens ni datos privados en esta carpeta.
