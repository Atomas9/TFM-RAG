"""Traducción de filtros de Chroma a consultas SQL parametrizadas.

Este módulo no abre la base de datos ni ejecuta consultas. Por ahora, su única
responsabilidad es convertir el ``final_where`` del flujo RAG en una cláusula
SQL segura y en su lista separada de parámetros.
"""

from __future__ import annotations

import sqlite3
from typing import Literal


# Los nombres de columna no se pueden enviar como parámetros ``?``. Por eso
# solo permitimos los campos que existen en la tabla ``fire_snapshots`` y que
# pueden aparecer en los filtros actuales del proyecto.
ALLOWED_FIELDS = {
    "country",
    "autonomous_community_normalized",
    "province_normalized",
    "location_normalized",
    "status",
    "operational_status",
    "report_date_number",
}

SCALAR_OPERATORS = {
    "$ne": "!=",
    "$gte": ">=",
    "$lte": "<=",
}

LIST_OPERATORS = {
    "$in": "IN",
    "$nin": "NOT IN",
}

LOGICAL_OPERATORS = {
    "$and": "AND",
    "$or": "OR",
}

EXTREME_FUNCTIONS = {
    "min": "MIN",
    "max": "MAX",
}

COUNT_EXPRESSIONS = {
    "incidents": "COUNT(DISTINCT incident_key)",
    "snapshots": "COUNT(*)",
    "reports": "COUNT(DISTINCT source_sha256)",
}


def compile_where_to_sql(
    where: dict[str, object] | None,
) -> tuple[str, list[object]]:
    """Convierte un ``where`` de Chroma en SQL y parámetros separados.

    ``None`` representa una consulta sin filtros. En ese caso no se genera una
    cláusula SQL y la lista de parámetros queda vacía.
    """

    if where is None:
        return "", []

    sql, parameters = _compile_expression(where)
    return sql, parameters


def count_matches(
    connection: sqlite3.Connection,
    where: dict[str, object] | None,
    count_target: Literal["incidents", "snapshots", "reports"],
) -> int:
    """Cuenta incendios, snapshots o informes que cumplen el filtro."""

    if count_target not in COUNT_EXPRESSIONS:
        raise ValueError(
            "El objetivo debe ser 'incidents', 'snapshots' o 'reports'."
        )

    where_sql, parameters = compile_where_to_sql(where)
    count_expression = COUNT_EXPRESSIONS[count_target]
    query = (
        f"SELECT {count_expression} AS value "
        "FROM fire_snapshots"
    )

    if where_sql:
        query += f" WHERE {where_sql}"

    row = connection.execute(query, parameters).fetchone()
    return int(row[0])


def get_extreme_report_date(
    connection: sqlite3.Connection,
    where: dict[str, object] | None,
    operation: Literal["min", "max"],
) -> int | None:
    """Devuelve la fecha mínima o máxima que cumple el filtro recibido.

    SQLite calcula el extremo dentro de la base de datos. Python solo recibe
    el valor final, por lo que no es necesario cargar todos los snapshots.
    """

    if operation not in EXTREME_FUNCTIONS:
        raise ValueError(
            "La operación debe ser 'min' o 'max'."
        )

    where_sql, parameters = compile_where_to_sql(where)
    sql_function = EXTREME_FUNCTIONS[operation]

    query = (
        f"SELECT {sql_function}(report_date_number) AS value "
        "FROM fire_snapshots"
    )

    if where_sql:
        query += f" WHERE {where_sql}"

    row = connection.execute(query, parameters).fetchone()
    value = row[0]

    # MIN y MAX devuelven NULL cuando ninguna fila cumple el filtro.
    if value is None:
        return None

    return int(value)


def get_snapshot_ids_for_report_date(
    connection: sqlite3.Connection,
    where: dict[str, object] | None,
    report_date_number: int,
) -> list[str]:
    """Devuelve los IDs que cumplen el filtro en una fecha concreta."""

    where_sql, parameters = compile_where_to_sql(where)
    conditions: list[str] = []

    if where_sql:
        conditions.append(f"({where_sql})")

    conditions.append("report_date_number = ?")
    parameters.append(report_date_number)

    query = (
        "SELECT snapshot_id "
        "FROM fire_snapshots "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY snapshot_id"
    )

    rows = connection.execute(query, parameters).fetchall()
    return [str(row[0]) for row in rows]


def get_extreme_snapshot_ids(
    connection: sqlite3.Connection,
    where: dict[str, object] | None,
    operation: Literal["min", "max"],
) -> tuple[int | None, list[str]]:
    """Obtiene la fecha extrema y todos los snapshots de esa fecha."""

    report_date_number = get_extreme_report_date(
        connection=connection,
        where=where,
        operation=operation,
    )

    if report_date_number is None:
        return None, []

    snapshot_ids = get_snapshot_ids_for_report_date(
        connection=connection,
        where=where,
        report_date_number=report_date_number,
    )

    return report_date_number, snapshot_ids


def _compile_expression(
    expression: dict[str, object],
) -> tuple[str, list[object]]:
    """Compila recursivamente una condición o un grupo lógico."""

    if not isinstance(expression, dict) or len(expression) != 1:
        raise ValueError(
            "Cada expresión del filtro debe ser un diccionario "
            "con una única clave."
        )

    key, value = next(iter(expression.items()))

    if key in LOGICAL_OPERATORS:
        return _compile_logical_group(key, value)

    return _compile_field_condition(key, value)


def _compile_logical_group(
    operator: str,
    conditions: object,
) -> tuple[str, list[object]]:
    """Compila una lista de condiciones unidas mediante AND u OR."""

    if not isinstance(conditions, list) or not conditions:
        raise ValueError(
            f"El operador {operator!r} necesita una lista no vacía."
        )

    sql_parts: list[str] = []
    parameters: list[object] = []

    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValueError(
                f"Cada elemento de {operator!r} debe ser un diccionario."
            )

        condition_sql, condition_parameters = _compile_expression(condition)
        sql_parts.append(f"({condition_sql})")
        parameters.extend(condition_parameters)

    sql_operator = LOGICAL_OPERATORS[operator]
    return f" {sql_operator} ".join(sql_parts), parameters


def _compile_field_condition(
    field: str,
    condition: object,
) -> tuple[str, list[object]]:
    """Compila la igualdad directa o el operador aplicado a un campo."""

    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Campo SQL no permitido: {field!r}.")

    # Chroma representa la igualdad sencilla sin ``$eq``:
    # ``{"province_normalized": "leon"}``.
    if not isinstance(condition, dict):
        _validate_scalar(condition, field)
        return f"{field} = ?", [condition]

    if len(condition) != 1:
        raise ValueError(
            f"La condición de {field!r} debe tener un único operador."
        )

    operator, value = next(iter(condition.items()))

    if operator in SCALAR_OPERATORS:
        _validate_scalar(value, field)
        sql_operator = SCALAR_OPERATORS[operator]
        return f"{field} {sql_operator} ?", [value]

    if operator in LIST_OPERATORS:
        return _compile_list_condition(field, operator, value)

    raise ValueError(f"Operador SQL no permitido: {operator!r}.")


def _compile_list_condition(
    field: str,
    operator: str,
    values: object,
) -> tuple[str, list[object]]:
    """Compila una condición IN o NOT IN con sus parámetros."""

    if not isinstance(values, list) or not values:
        raise ValueError(
            f"El operador {operator!r} necesita una lista no vacía."
        )

    for value in values:
        _validate_scalar(value, field)

    placeholders = ", ".join("?" for _ in values)
    sql_operator = LIST_OPERATORS[operator]
    return f"{field} {sql_operator} ({placeholders})", list(values)


def _validate_scalar(value: object, field: str) -> None:
    """Rechaza listas, diccionarios y valores nulos donde se espera escalar."""

    if type(value) not in {str, int, float, bool}:
        raise ValueError(
            f"El campo {field!r} necesita un valor escalar no nulo."
        )
