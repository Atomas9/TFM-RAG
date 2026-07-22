"""Interpretacion determinista de filtros de metadatos para ChromaDB.

Este modulo no abre Chroma ni genera embeddings. Su responsabilidad termina en
dos operaciones puras y faciles de probar:

1. convertir una pregunta en un objeto :class:`ParsedQuery`;
2. convertir sus filtros en el diccionario ``where`` que entiende Chroma.

El vocabulario geografico se construye con los metadatos reales de la
coleccion. De este modo, las nuevas localizaciones quedan disponibles tras
reindexar los PDF sin tener que modificar este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
import unicodedata
from typing import Iterable, Literal

from pydantic import BaseModel, Field


SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

MONTH_PATTERN = "|".join(SPANISH_MONTHS)

COUNTRY_ALIASES = {
    "espana": "ES",
    "territorio espanol": "ES",
    "portugal": "PT",
}

SPANISH_COMMUNITIES = {
    "andalucia": "andalucia",
    "aragon": "aragon",
    "asturias": "asturias",
    "principado de asturias": "asturias",
    "cantabria": "cantabria",
    "castilla-la mancha": "castilla-la mancha",
    "castilla la mancha": "castilla-la mancha",
    "castilla y leon": "castilla y leon",
    "cataluna": "cataluna",
    "catalunya": "cataluna",
    "ceuta": "ceuta",
    "comunitat valenciana": "comunitat valenciana",
    "comunidad valenciana": "comunitat valenciana",
    "c. valenciana": "comunitat valenciana",
    "extremadura": "extremadura",
    "galicia": "galicia",
    "illes balears": "illes balears",
    "islas baleares": "illes balears",
    "baleares": "illes balears",
    "la rioja": "la rioja",
    "comunidad de madrid": "comunidad de madrid",
    "madrid": "comunidad de madrid",
    "melilla": "melilla",
    "region de murcia": "region de murcia",
    "murcia": "region de murcia",
    "navarra": "navarra",
    "comunidad foral de navarra": "navarra",
    "pais vasco": "pais vasco",
    "euskadi": "pais vasco",
    "canarias": "canarias",
}

SPANISH_PROVINCES = {
    "a coruna": "a coruna",
    "coruna": "a coruna",
    "alava": "alava",
    "araba": "alava",
    "albacete": "albacete",
    "alicante": "alicante",
    "alacant": "alicante",
    "almeria": "almeria",
    "asturias": "asturias",
    "avila": "avila",
    "badajoz": "badajoz",
    "barcelona": "barcelona",
    "bizkaia": "bizkaia",
    "vizcaya": "bizkaia",
    "burgos": "burgos",
    "caceres": "caceres",
    "cadiz": "cadiz",
    "cantabria": "cantabria",
    "castellon": "castellon",
    "castello": "castellon",
    "ceuta": "ceuta",
    "ciudad real": "ciudad real",
    "cordoba": "cordoba",
    "cuenca": "cuenca",
    "girona": "girona",
    "gerona": "girona",
    "granada": "granada",
    "guadalajara": "guadalajara",
    "gipuzkoa": "gipuzkoa",
    "guipuzcoa": "gipuzkoa",
    "huelva": "huelva",
    "huesca": "huesca",
    "illes balears": "illes balears",
    "baleares": "illes balears",
    "jaen": "jaen",
    "la rioja": "la rioja",
    "las palmas": "las palmas",
    "leon": "leon",
    "lleida": "lleida",
    "lerida": "lleida",
    "lugo": "lugo",
    "madrid": "madrid",
    "malaga": "malaga",
    "melilla": "melilla",
    "murcia": "murcia",
    "navarra": "navarra",
    "ourense": "ourense",
    "orense": "ourense",
    "palencia": "palencia",
    "pontevedra": "pontevedra",
    "salamanca": "salamanca",
    "santa cruz de tenerife": "santa cruz de tenerife",
    "segovia": "segovia",
    "sevilla": "sevilla",
    "soria": "soria",
    "tarragona": "tarragona",
    "teruel": "teruel",
    "toledo": "toledo",
    "valencia": "valencia",
    "valladolid": "valladolid",
    "zamora": "zamora",
    "zaragoza": "zaragoza",
}

COMMUNITY_ALIASES = {
    "principado de asturias": "asturias",
    "castilla la mancha": "castilla-la mancha",
    "comunidad valenciana": "comunitat valenciana",
    "c. valenciana": "comunitat valenciana",
    "catalunya": "cataluna",
    "euskadi": "pais vasco",
    "islas baleares": "illes balears",
    "baleares": "illes balears",
    "madrid": "comunidad de madrid",
    "murcia": "region de murcia",
    "comunidad foral de navarra": "navarra",
}

PROVINCE_ALIASES = {
    "coruna": "a coruna",
    "araba": "alava",
    "vizcaya": "bizkaia",
    "alacant": "alicante",
    "castello": "castellon",
    "gerona": "girona",
    "guipuzcoa": "gipuzkoa",
    "lerida": "lleida",
    "orense": "ourense",
    "baleares": "illes balears",
}

STATUS_ALIASES = {
    "activo": "ACTIVO",
    "activos": "ACTIVO",
    "activa": "ACTIVO",
    "activas": "ACTIVO",
    "controlado": "CONTROLADO",
    "controlados": "CONTROLADO",
    "controlada": "CONTROLADO",
    "controladas": "CONTROLADO",
    "estabilizado": "ESTABILIZADO",
    "estabilizados": "ESTABILIZADO",
    "estabilizada": "ESTABILIZADO",
    "estabilizadas": "ESTABILIZADO",
    "extinguido": "EXTINGUIDO",
    "extinguidos": "EXTINGUIDO",
    "extinguida": "EXTINGUIDO",
    "extinguidas": "EXTINGUIDO",
}


class MetadataCatalog(BaseModel):
    """Valores consultables que existen en la coleccion actual."""

    countries: dict[str, str] = Field(default_factory=dict)
    communities: dict[str, str] = Field(default_factory=dict)
    provinces: dict[str, str] = Field(default_factory=dict)
    locations: dict[str, str] = Field(default_factory=dict)
    statuses: dict[str, str] = Field(default_factory=dict)
    operational_statuses: dict[str, str] = Field(default_factory=dict)
    report_years: list[int] = Field(default_factory=list)

    @classmethod
    def from_metadatas(
        cls,
        metadatas: Iterable[dict[str, object]],
    ) -> "MetadataCatalog":
        """Construye alias a partir de los metadatos planos de Chroma."""

        countries: dict[str, str] = dict(COUNTRY_ALIASES)
        communities: dict[str, str] = dict(SPANISH_COMMUNITIES)
        provinces: dict[str, str] = dict(SPANISH_PROVINCES)
        locations: dict[str, str] = {}
        statuses: dict[str, str] = dict(STATUS_ALIASES)
        operational_statuses: dict[str, str] = {}
        report_years: set[int] = set()

        metadata_rows = list(metadatas)

        for metadata in metadata_rows:
            _add_metadata_aliases(
                communities,
                metadata.get("autonomous_community"),
                metadata.get("autonomous_community_normalized"),
            )
            _add_metadata_aliases(
                provinces,
                metadata.get("province"),
                metadata.get("province_normalized"),
            )
            _add_metadata_aliases(
                locations,
                metadata.get("location"),
                metadata.get("location_normalized"),
            )

            location = metadata.get("location_normalized")
            if isinstance(location, str) and "," in location:
                name, article = [part.strip() for part in location.split(",", 1)]
                if name and article:
                    locations[f"{article} {name}"] = location

            status = metadata.get("status")
            if isinstance(status, str) and status:
                statuses[normalize_query_text(status)] = status

            operational_status = metadata.get("operational_status")
            if isinstance(operational_status, str) and operational_status:
                operational_statuses[
                    normalize_query_text(operational_status)
                ] = operational_status

            report_date_number = metadata.get("report_date_number")
            if isinstance(report_date_number, int):
                report_years.add(report_date_number // 10_000)

        for alias, canonical in COMMUNITY_ALIASES.items():
            communities[normalize_query_text(alias)] = canonical

        for alias, canonical in PROVINCE_ALIASES.items():
            provinces[normalize_query_text(alias)] = canonical

        existing_statuses = set(statuses.values())
        for alias, canonical in STATUS_ALIASES.items():
            if canonical in existing_statuses:
                statuses[alias] = canonical

        return cls(
            countries=countries,
            communities=communities,
            provinces=provinces,
            locations=locations,
            statuses=statuses,
            operational_statuses=operational_statuses,
            report_years=sorted(report_years),
        )


class MetadataFilters(BaseModel):
    """Filtros incluidos y excluidos antes de traducirlos a Chroma."""

    included_countries: list[str] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)

    included_communities: list[str] = Field(default_factory=list)
    excluded_communities: list[str] = Field(default_factory=list)

    included_provinces: list[str] = Field(default_factory=list)
    excluded_provinces: list[str] = Field(default_factory=list)

    included_locations: list[str] = Field(default_factory=list)
    excluded_locations: list[str] = Field(default_factory=list)

    included_statuses: list[str] = Field(default_factory=list)
    excluded_statuses: list[str] = Field(default_factory=list)

    included_operational_statuses: list[str] = Field(default_factory=list)
    excluded_operational_statuses: list[str] = Field(default_factory=list)

    report_date_from: int | None = None
    report_date_to: int | None = None


class ParsedQuery(BaseModel):
    """Resultado explicable del analisis de una pregunta."""

    original_query: str
    normalized_query: str
    semantic_query: str
    filters: MetadataFilters
    ambiguities: list[str] = Field(default_factory=list)


EntityKind = Literal[
    "country",
    "community",
    "province",
    "location",
    "status",
    "operational_status",
]


@dataclass(frozen=True)
class _EntityMatch:
    kind: EntityKind
    value: str
    alias: str
    start: int
    end: int


NEGATION_BEFORE_ENTITY = re.compile(
    r"(?:"
    r"\b(?:pero\s+)?no(?:\s+(?:sea|sean|es|son|este|esten))?"
    r"(?:\s+(?:de|del|en|los|las))?"
    r"|\bexcepto(?:\s+(?:los|las))?(?:\s+de)?"
    r"|\bsalvo(?:\s+(?:los|las))?(?:\s+de)?"
    r"|\bmenos(?:\s+(?:los|las))?(?:\s+de)?"
    r"|\bfuera\s+de"
    r")\s*$"
)

OPERATIONAL_STATUS_PATTERN = re.compile(
    r"\b(?:situacion\s+operativa|s\.?\s*o\.?)\s*"
    r"(?:(?:numero|nivel)\s*)?:?\s*(se|[0-3])\b"
)

TEXTUAL_RANGE_PATTERNS = (
    re.compile(
        rf"\bentre\s+(?:el\s+)?(?P<day_from>\d{{1,2}})"
        rf"(?:\s+de\s+(?P<month_from>{MONTH_PATTERN}))?\s+y\s+"
        rf"(?:el\s+)?(?P<day_to>\d{{1,2}})\s+de\s+"
        rf"(?P<month_to>{MONTH_PATTERN})(?:\s+de\s+(?P<year>\d{{4}}))?\b"
    ),
    re.compile(
        rf"\bdel\s+(?P<day_from>\d{{1,2}})"
        rf"(?:\s+de\s+(?P<month_from>{MONTH_PATTERN}))?\s+al\s+"
        rf"(?P<day_to>\d{{1,2}})\s+de\s+"
        rf"(?P<month_to>{MONTH_PATTERN})(?:\s+de\s+(?P<year>\d{{4}}))?\b"
    ),
)

TEXTUAL_DATE_PATTERN = re.compile(
    rf"\b(?P<day>\d{{1,2}})\s+de\s+(?P<month>{MONTH_PATTERN})"
    rf"(?:\s+de\s+(?P<year>\d{{4}}))?\b"
)

NUMERIC_DATE_PATTERN = re.compile(
    r"\b(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})\b"
)

ISO_DATE_PATTERN = re.compile(
    r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b"
)


def normalize_query_text(text: str) -> str:
    """Normaliza tildes, mayusculas y espacios sin reordenar la frase."""

    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


def parse_metadata_filters(
    query: str,
    catalog: MetadataCatalog,
) -> ParsedQuery:
    """Interpreta entidades, negaciones, contrastes y fechas conocidas."""

    if not query.strip():
        raise ValueError("La consulta no puede estar vacia.")

    normalized_query = normalize_query_text(query)
    filters = MetadataFilters()
    ambiguities: list[str] = []

    matches = _find_entity_matches(normalized_query, catalog)
    previous_match: _EntityMatch | None = None
    previous_excluded = False

    for entity_match in matches:
        excluded = _is_explicitly_excluded(
            normalized_query,
            entity_match.start,
        )

        if (
            not excluded
            and previous_match is not None
            and previous_excluded
            and previous_match.kind == entity_match.kind
            and _is_simple_coordination(
                normalized_query[previous_match.end : entity_match.start]
            )
        ):
            excluded = True

        _add_entity_to_filters(filters, entity_match, excluded)
        previous_match = entity_match
        previous_excluded = excluded

    _extract_report_dates(
        normalized_query,
        catalog,
        filters,
        ambiguities,
    )
    _deduplicate_filter_values(filters)
    _find_filter_contradictions(filters, ambiguities)

    return ParsedQuery(
        original_query=query,
        normalized_query=normalized_query,
        semantic_query=query.strip(),
        filters=filters,
        ambiguities=ambiguities,
    )


def build_chroma_where(filters: MetadataFilters) -> dict[str, object] | None:
    """Traduce filtros estructurados a la sintaxis ``where`` de Chroma."""

    conditions: list[dict[str, object]] = []

    categorical_fields = (
        (
            "country",
            filters.included_countries,
            filters.excluded_countries,
        ),
        (
            "autonomous_community_normalized",
            filters.included_communities,
            filters.excluded_communities,
        ),
        (
            "province_normalized",
            filters.included_provinces,
            filters.excluded_provinces,
        ),
        (
            "location_normalized",
            filters.included_locations,
            filters.excluded_locations,
        ),
        (
            "status",
            filters.included_statuses,
            filters.excluded_statuses,
        ),
        (
            "operational_status",
            filters.included_operational_statuses,
            filters.excluded_operational_statuses,
        ),
    )

    for field_name, included, excluded in categorical_fields:
        overlap = set(included) & set(excluded)
        if overlap:
            values = ", ".join(sorted(overlap))
            raise ValueError(
                f"Valores incluidos y excluidos simultaneamente en "
                f"{field_name}: {values}"
            )

        if included:
            if len(included) == 1:
                conditions.append({field_name: included[0]})
            else:
                conditions.append({field_name: {"$in": included}})
        elif excluded:
            if len(excluded) == 1:
                conditions.append({field_name: {"$ne": excluded[0]}})
            else:
                conditions.append({field_name: {"$nin": excluded}})

    date_from = filters.report_date_from
    date_to = filters.report_date_to

    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("La fecha inicial no puede ser posterior a la final.")

    if date_from is not None and date_from == date_to:
        conditions.append({"report_date_number": date_from})
    else:
        if date_from is not None:
            conditions.append(
                {"report_date_number": {"$gte": date_from}}
            )
        if date_to is not None:
            conditions.append(
                {"report_date_number": {"$lte": date_to}}
            )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _add_metadata_aliases(
    aliases: dict[str, str],
    display_value: object,
    normalized_value: object,
) -> None:
    if not isinstance(normalized_value, str) or not normalized_value:
        return

    canonical = normalize_query_text(normalized_value)
    aliases[canonical] = canonical

    if isinstance(display_value, str) and display_value:
        aliases[normalize_query_text(display_value)] = canonical


def _find_entity_matches(
    normalized_query: str,
    catalog: MetadataCatalog,
) -> list[_EntityMatch]:
    candidates: list[_EntityMatch] = []

    entity_catalogs: tuple[tuple[EntityKind, dict[str, str]], ...] = (
        ("country", catalog.countries),
        ("community", catalog.communities),
        ("province", catalog.provinces),
        ("location", catalog.locations),
        ("status", catalog.statuses),
    )

    for kind, aliases in entity_catalogs:
        for alias, value in aliases.items():
            if not alias:
                continue
            pattern = re.compile(
                rf"(?<!\w){re.escape(alias)}(?!\w)"
            )
            for match in pattern.finditer(normalized_query):
                candidates.append(
                    _EntityMatch(
                        kind=kind,
                        value=value,
                        alias=alias,
                        start=match.start(),
                        end=match.end(),
                    )
                )

    for match in OPERATIONAL_STATUS_PATTERN.finditer(normalized_query):
        value = match.group(1).upper()
        candidates.append(
            _EntityMatch(
                kind="operational_status",
                value=value,
                alias=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    kind_priority = {
        "country": 0,
        "community": 1,
        "province": 2,
        "location": 3,
        "status": 4,
        "operational_status": 5,
    }
    def candidate_priority(item: _EntityMatch) -> tuple[int, int, int, int]:
        prefix = normalized_query[max(0, item.start - 35) : item.start]
        contextual_priority = 1
        if item.kind == "province" and re.search(
            r"\bprovincia\s+(?:de\s+)?$",
            prefix,
        ):
            contextual_priority = 0
        elif item.kind == "community" and re.search(
            r"\bcomunidad(?:\s+autonoma)?\s+(?:de\s+)?$",
            prefix,
        ):
            contextual_priority = 0

        return (
            -(item.end - item.start),
            contextual_priority,
            kind_priority[item.kind],
            item.start,
        )

    candidates.sort(key=candidate_priority)

    accepted: list[_EntityMatch] = []
    for candidate in candidates:
        if any(
            candidate.start < existing.end
            and candidate.end > existing.start
            for existing in accepted
        ):
            continue
        accepted.append(candidate)

    return sorted(accepted, key=lambda item: item.start)


def _is_explicitly_excluded(text: str, entity_start: int) -> bool:
    prefix = text[max(0, entity_start - 80) : entity_start]
    return NEGATION_BEFORE_ENTITY.search(prefix) is not None


def _is_simple_coordination(separator: str) -> bool:
    simplified = re.sub(r"[\s,;]+", " ", separator).strip()
    return simplified in {"", "y", "e", "o", "u", "ni"}


def _add_entity_to_filters(
    filters: MetadataFilters,
    entity_match: _EntityMatch,
    excluded: bool,
) -> None:
    attribute_by_kind = {
        ("country", False): "included_countries",
        ("country", True): "excluded_countries",
        ("community", False): "included_communities",
        ("community", True): "excluded_communities",
        ("province", False): "included_provinces",
        ("province", True): "excluded_provinces",
        ("location", False): "included_locations",
        ("location", True): "excluded_locations",
        ("status", False): "included_statuses",
        ("status", True): "excluded_statuses",
        ("operational_status", False): "included_operational_statuses",
        ("operational_status", True): "excluded_operational_statuses",
    }
    attribute_name = attribute_by_kind[(entity_match.kind, excluded)]
    getattr(filters, attribute_name).append(entity_match.value)


def _extract_report_dates(
    normalized_query: str,
    catalog: MetadataCatalog,
    filters: MetadataFilters,
    ambiguities: list[str],
) -> None:
    for pattern in TEXTUAL_RANGE_PATTERNS:
        match = pattern.search(normalized_query)
        if not match:
            continue

        year = _resolve_year(match.group("year"), catalog, ambiguities)
        if year is None:
            return

        month_to = SPANISH_MONTHS[match.group("month_to")]
        month_from_text = match.group("month_from")
        month_from = (
            SPANISH_MONTHS[month_from_text]
            if month_from_text
            else month_to
        )
        date_from = _safe_date(
            year,
            month_from,
            int(match.group("day_from")),
            ambiguities,
        )
        date_to = _safe_date(
            year,
            month_to,
            int(match.group("day_to")),
            ambiguities,
        )
        if date_from and date_to:
            filters.report_date_from = _date_number(date_from)
            filters.report_date_to = _date_number(date_to)
        return

    date_matches: list[tuple[re.Match[str], date]] = []

    for pattern in (ISO_DATE_PATTERN, NUMERIC_DATE_PATTERN):
        for match in pattern.finditer(normalized_query):
            parsed_date = _safe_date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
                ambiguities,
            )
            if parsed_date:
                date_matches.append((match, parsed_date))

    if not date_matches:
        for match in TEXTUAL_DATE_PATTERN.finditer(normalized_query):
            year = _resolve_year(match.group("year"), catalog, ambiguities)
            if year is None:
                continue
            parsed_date = _safe_date(
                year,
                SPANISH_MONTHS[match.group("month")],
                int(match.group("day")),
                ambiguities,
            )
            if parsed_date:
                date_matches.append((match, parsed_date))

    if not date_matches:
        return
    if len(date_matches) > 1:
        ambiguities.append(
            "Se detectaron varias fechas sin una construccion de rango soportada."
        )
        return

    match, parsed_date = date_matches[0]
    prefix = normalized_query[max(0, match.start() - 40) : match.start()]

    if re.search(
        r"(?:\bdesde\s+(?:el\s+)?|\ba\s+partir\s+(?:de\s+el|del|de)\s+)$",
        prefix,
    ):
        filters.report_date_from = _date_number(parsed_date)
    elif re.search(
        r"(?:\bdespues\s+(?:de|del)|\bposteriores?\s+al?)\s*$",
        prefix,
    ):
        filters.report_date_from = _date_number(parsed_date + timedelta(days=1))
    elif re.search(r"(?:\bhasta)\s+(?:el\s+)?$", prefix):
        filters.report_date_to = _date_number(parsed_date)
    elif re.search(
        r"(?:\bantes\s+(?:de|del)|\banteriores?\s+al?)\s*$",
        prefix,
    ):
        filters.report_date_to = _date_number(parsed_date - timedelta(days=1))
    else:
        date_number = _date_number(parsed_date)
        filters.report_date_from = date_number
        filters.report_date_to = date_number


def _resolve_year(
    explicit_year: str | None,
    catalog: MetadataCatalog,
    ambiguities: list[str],
) -> int | None:
    if explicit_year:
        return int(explicit_year)
    if len(catalog.report_years) == 1:
        return catalog.report_years[0]

    ambiguities.append(
        "La fecha no incluye ano y el corpus no tiene un unico ano de referencia."
    )
    return None


def _safe_date(
    year: int,
    month: int,
    day: int,
    ambiguities: list[str],
) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        ambiguities.append(
            f"La fecha detectada no es valida: {day:02d}/{month:02d}/{year}."
        )
        return None


def _date_number(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _deduplicate_filter_values(filters: MetadataFilters) -> None:
    for field_name in type(filters).model_fields:
        value = getattr(filters, field_name)
        if isinstance(value, list):
            setattr(filters, field_name, list(dict.fromkeys(value)))


def _find_filter_contradictions(
    filters: MetadataFilters,
    ambiguities: list[str],
) -> None:
    pairs = (
        ("pais", filters.included_countries, filters.excluded_countries),
        (
            "comunidad autonoma",
            filters.included_communities,
            filters.excluded_communities,
        ),
        ("provincia", filters.included_provinces, filters.excluded_provinces),
        (
            "localizacion",
            filters.included_locations,
            filters.excluded_locations,
        ),
        ("estado", filters.included_statuses, filters.excluded_statuses),
        (
            "situacion operativa",
            filters.included_operational_statuses,
            filters.excluded_operational_statuses,
        ),
    )

    for label, included, excluded in pairs:
        for value in sorted(set(included) & set(excluded)):
            ambiguities.append(
                f"El valor {value!r} aparece incluido y excluido como {label}."
            )
