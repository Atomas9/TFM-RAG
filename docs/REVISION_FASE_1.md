# Revision de la fase 1

Fecha de revision: 2026-07-15.

Archivo revisado: `src/miteco_rag/parseo_y_chuncking.py`.

## Funcionalidad comprobada

- La ruta `data/raw/miteco` se resuelve correctamente al ejecutar desde la raiz
  del repositorio.
- PyMuPDF abre los cuatro documentos y extrae texto pagina a pagina.
- Cada linea conserva pagina, numero de linea, texto original, texto limpio y
  texto normalizado.
- `clean_line` elimina correctamente espacios sobrantes.
- `normalize_text` elimina diacriticos y convierte el texto a minusculas.
- `calculate_sha256` produce un hash diferente y estable para cada PDF.
- La fecha principal se extrae del contenido del documento.
- La ultima actualizacion se extrae correctamente cuando esta presente.
- El tipo de parte se identifica como `definitivo` a partir del nombre.
- `DocumentMetadata` valida correctamente los metadatos con Pydantic.

## Resultados sobre el corpus actual

| Documento | Fecha del parte | Lineas | Localizaciones |
| --- | --- | ---: | ---: |
| `ActuacionesMITECO-definitivo.pdf` | 2026-07-05 | 161 | 9 |
| `ActuacionesMITECO-definitivo-12072026.pdf` | 2026-07-12 | 154 | 9 |
| `ActuacionesMITECO-definitivo13072026.pdf` | 2026-07-13 | 156 | 10 |
| `ActuacionesMITECO-definitivo14072026.pdf` | 2026-07-14 | 121 | 6 |

Total provisional antes de construir bloques: 34 localizaciones. De ellas, 33
corresponden a Espana y una a Portugal.

## Mejoras recomendadas antes del chunking

1. Mover las instrucciones de prueba del final a una funcion `main` y
   protegerlas con `if __name__ == "__main__"`. Actualmente el archivo imprime
   y procesa el primer PDF tambien cuando se importa desde otro modulo.
2. Comprobar que `all_pdf` contiene elementos antes de acceder a `all_pdf[0]`.
3. Declarar `extract_pdf_lines` como `list[PDFLine]` y tipar tambien la lista
   interna para mejorar el autocompletado.
4. Eliminar temporalmente los imports no utilizados (`timezone` e `Iterable`)
   o conservarlos solo cuando se implementen el informe y la exportacion.
5. Decidir si `last_update` se almacenara como hora local sin zona o como
   fecha-hora con la zona `Europe/Madrid`.
6. Considerar `ConfigDict(extra="forbid")` y restricciones `Field(ge=1)` para
   que Pydantic detecte campos mal escritos y paginas invalidas.
7. Mantener el nombre `parseo_y_chuncking.py` mientras se estudia el flujo, pero
   corregir finalmente `chuncking` a `chunking` antes de exponerlo como modulo
   estable.

## Siguiente incremento

Crear catalogos normalizados de comunidades y provincias y, despues,
implementar una maquina de estados que conserve comunidad y provincia entre
localizaciones consecutivas. Todavia no corresponde extraer embeddings ni
insertar datos en ChromaDB.

