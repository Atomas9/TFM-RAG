# Revision del retrieval semantico e hibrido

Fecha de revision: 2026-07-22.

Archivos revisados:

- `src/miteco_rag/query_filters.py`;
- `src/miteco_rag/retrieval_chroma_solution.py`;
- `tests/test_query_filters.py`;
- `tests/test_retrieval_chroma.py`;
- coleccion local `MITECO_fire_snapshots`.

## Estado alcanzado

La recuperacion ya no depende exclusivamente de la proximidad entre
embeddings. El sistema puede limitar la busqueda vectorial mediante metadatos
extraidos de la pregunta de forma determinista.

`query_filters.py` contiene:

- `MetadataCatalog`, construido con catalogos geograficos controlados y los
  valores reales de Chroma;
- `MetadataFilters`, que separa inclusiones y exclusiones por campo;
- `ParsedQuery`, que conserva la interpretacion y sus posibles ambiguedades;
- `parse_metadata_filters()`, que analiza la pregunta;
- `build_chroma_where()`, que genera el filtro final sin consultar la base;
- `metadata_query()`, que unifica ambos pasos para el codigo cliente.

`retrieval_chroma_solution.py` contiene:

- apertura robusta de la coleccion persistente;
- construccion del catalogo de consulta;
- retrieval vectorial con un `where` opcional;
- retrieval hibrido que devuelve resultados, interpretacion y filtro;
- salida legible con distancia, geografia, fecha, estado y chunk;
- una entrada `main()` protegida para evitar consultas al importar el modulo.

`retrieval_chroma.py` conserva la version desarrollada por el alumno antes de
esta solucion, para que pueda continuar el ejercicio sin tener el archivo
resuelto encima.

El parametro opcional `model` permite reutilizar BGE-M3 en varias consultas y
usar dobles ligeros durante las pruebas. El parametro `db_collection` cumple el
mismo objetivo con Chroma.

## Lenguaje determinista soportado

La primera version reconoce:

- paises incluidos o excluidos;
- comunidades autonomas;
- provincias, aunque no aparezcan en el corpus actual;
- localizaciones existentes en la coleccion;
- estados del incendio en singular, plural y genero variable;
- situaciones operativas `SE`, `0`, `1`, `2` y `3`;
- fecha exacta del parte;
- meses y anos traducidos a intervalos de fechas;
- intervalos como `entre el 12 y el 15 de julio`;
- comparaciones como `antes del` y `despues del`;
- negaciones con `no`, `excepto`, `salvo`, `menos` y `fuera de`;
- listas coordinadas con `y`, `o` y `ni`;
- contrastes como `no de Leon sino de Palencia`;
- consultas presentes mediante `hay`, `existen`, `actualmente`, `ahora`,
  `hoy`, `a dia de hoy`, `en este momento` y `ultimo parte`;
- consultas historicas con formas como `estuvieron activos` o `han estado
  activos`.

Las entidades mas largas tienen prioridad. Por ello `Castilla y Leon` se
interpreta como comunidad y no como una aparicion de la provincia de Leon. Los
contextos `provincia de Madrid` y `comunidad de Madrid` resuelven esa colision
de forma explicita.

Si un mismo valor queda incluido y excluido, `ParsedQuery` registra una
ambiguedad y el retrieval se detiene antes de cargar el modelo o consultar por
similitud.

## Validacion automatizada

La suite contiene 38 pruebas:

- 34 pruebas puras del analizador, del constructor y de `metadata_query()`;
- 4 pruebas de integracion interna con dobles de modelo y coleccion.

Resultado:

```text
38 passed
```

Las pruebas no requieren PDF, Chroma, red ni descarga de BGE-M3. Tambien se
comprobo la compilacion de los modulos y la ausencia de errores de formato en
el diff.

## Validacion con la coleccion real

La consulta `Hay incendios activos en Leon?` genera actualmente:

```python
{
    "$and": [
        {"province_normalized": "leon"},
        {"status": "ACTIVO"},
        {"report_date_number": 20260719},
    ]
}
```

No hay resultados porque el ultimo parte global, fechado el 19 de julio, no
contiene incendios de Leon con estado activo. La consulta historica `Que
incendios estuvieron activos en Leon?` omite la fecha maxima y recupera los
cinco snapshots historicos de esa provincia.

Se validaron ademas los siguientes filtros directamente con Chroma:

| Consulta | Registros | Comprobacion |
| --- | ---: | --- |
| Activos, pero no de Leon | 1 | Activo y fuera de Leon en el ultimo parte |
| Estuvieron activos en Leon | 5 | Consulta historica sin fecha maxima |
| Fuegos que hay en Leon y Palencia | 0 | `$in` geografico y ultimo parte |
| No de Leon, sino de Palencia | 0 | Palencia se interpreta como inclusion |
| Incendios en Huelva | 0 | Provincia reconocida aunque no haya datos |
| Incendios de Castilla y Leon | 9 | Todos de esa comunidad |
| Incendios fuera de Espana | 1 | Unico snapshot de Portugal |
| Entre el 12 y el 15 de julio | 30 | Fechas dentro del intervalo |
| Situacion operativa 2 de Aragon | 6 | Ambas condiciones satisfechas |

## Limites conocidos

1. El analizador cubre construcciones declaradas y probadas, no cualquier frase
   posible en espanol.
2. Una localizacion que no exista en Chroma no puede reconocerse como tal; las
   provincias y comunidades si disponen de catalogos completos.
3. Los nombres presentes como origen de medios pueden parecer entidades
   geograficas si la pregunta no deja claro que se refiere al incendio.
4. Las fechas sin ano solo se resuelven automaticamente cuando el corpus tiene
   un unico ano.
5. Las fechas interpretadas son fechas del parte, no fechas de inicio del
   incendio.
6. La consulta automatica usa siempre ranking vectorial, incluso cuando todos
   los criterios son estructurados.
7. Todavia no existe busqueda lexica con puntuacion ni fusion de rankings.
8. No se ha definido un umbral de distancia para rechazar resultados poco
   relevantes.
9. La deteccion temporal es determinista y solo cubre las construcciones
   documentadas; la siguiente version evaluara un parser asistido por LLM.

## Siguiente incremento recomendado

Evaluar un LLM como parser de una intencion estructurada y validada con
Pydantic, manteniendo esta version determinista como linea base. El LLM no debe
generar directamente diccionarios `where` sin validacion.
