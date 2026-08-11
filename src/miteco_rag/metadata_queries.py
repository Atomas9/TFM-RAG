"""Traducción de filtros de Chroma a consultas SQL parametrizadas.

Este módulo no abre la base de datos ni ejecuta consultas. Por ahora, su única
responsabilidad es convertir el ``final_where`` del flujo RAG en una cláusula
SQL segura y en su lista separada de parámetros.
"""

from __future__ import annotations


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
