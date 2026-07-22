"""Pruebas del analizador determinista de filtros de metadatos."""

import pytest

from miteco_rag.query_filters import (
    MetadataCatalog,
    MetadataFilters,
    build_chroma_where,
    parse_metadata_filters,
)


@pytest.fixture
def catalog() -> MetadataCatalog:
    """Catalogo pequeno que no depende de los datos locales ni de Chroma."""

    return MetadataCatalog.from_metadatas(
        [
            {
                "country": "ES",
                "autonomous_community": "Castilla y León",
                "autonomous_community_normalized": "castilla y leon",
                "province": "León",
                "province_normalized": "leon",
                "location": "VILLABLINO",
                "location_normalized": "villablino",
                "status": "ACTIVO",
                "operational_status": "1",
                "report_date_number": 20260712,
            },
            {
                "country": "ES",
                "autonomous_community": "Castilla-La Mancha",
                "autonomous_community_normalized": "castilla-la mancha",
                "province": "Guadalajara",
                "province_normalized": "guadalajara",
                "location": "MIERLA, LA",
                "location_normalized": "mierla, la",
                "status": "CONTROLADO",
                "operational_status": "2",
                "report_date_number": 20260715,
            },
            {
                "country": "PT",
                "autonomous_community": None,
                "autonomous_community_normalized": None,
                "province": "Portugal",
                "province_normalized": "portugal",
                "location": "PONTE DA BARCA",
                "location_normalized": "ponte da barca",
                "status": "ACTIVO",
                "operational_status": "SE",
                "report_date_number": 20260715,
            },
        ]
    )


def parse_where(question: str, catalog: MetadataCatalog) -> dict | None:
    parsed = parse_metadata_filters(question, catalog)
    assert parsed.ambiguities == []
    return build_chroma_where(parsed.filters)


def test_active_fires_in_leon(catalog: MetadataCatalog) -> None:
    assert parse_where("Incendios activos en León", catalog) == {
        "$and": [
            {"province_normalized": "leon"},
            {"status": "ACTIVO"},
        ]
    }


def test_excludes_leon(catalog: MetadataCatalog) -> None:
    assert parse_where(
        "Dime incendios activos, pero no de León",
        catalog,
    ) == {
        "$and": [
            {"province_normalized": {"$ne": "leon"}},
            {"status": "ACTIVO"},
        ]
    }


def test_not_leon_but_palencia_prioritizes_palencia(
    catalog: MetadataCatalog,
) -> None:
    parsed = parse_metadata_filters(
        "Incendios no de León, sino de Palencia",
        catalog,
    )

    assert parsed.filters.excluded_provinces == ["leon"]
    assert parsed.filters.included_provinces == ["palencia"]
    assert build_chroma_where(parsed.filters) == {
        "province_normalized": "palencia"
    }


def test_multiple_provinces_use_in_operator(catalog: MetadataCatalog) -> None:
    assert parse_where("Incendios de León o Palencia", catalog) == {
        "province_normalized": {"$in": ["leon", "palencia"]}
    }


def test_castilla_y_leon_is_not_parsed_as_province(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendios de Castilla y León", catalog) == {
        "autonomous_community_normalized": "castilla y leon"
    }


def test_exclusion_propagates_across_coordinated_provinces(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where(
        "Incendios excepto los de León y Palencia",
        catalog,
    ) == {
        "province_normalized": {"$nin": ["leon", "palencia"]}
    }


def test_absent_but_valid_province_is_still_recognized(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendios en Huelva", catalog) == {
        "province_normalized": "huelva"
    }


def test_location_catalog_accepts_inverted_article(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendio de La Mierla", catalog) == {
        "location_normalized": "mierla, la"
    }


def test_province_context_resolves_madrid_collision(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendios de la provincia de Madrid", catalog) == {
        "province_normalized": "madrid"
    }


def test_community_context_resolves_madrid_collision(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendios de la comunidad de Madrid", catalog) == {
        "autonomous_community_normalized": "comunidad de madrid"
    }


def test_country_exclusion(catalog: MetadataCatalog) -> None:
    assert parse_where("Incendios fuera de España", catalog) == {
        "country": {"$ne": "ES"}
    }


def test_operational_status_and_community(catalog: MetadataCatalog) -> None:
    assert parse_where(
        "Incendios en situación operativa 2 de Aragón",
        catalog,
    ) == {
        "$and": [
            {"autonomous_community_normalized": "aragon"},
            {"operational_status": "2"},
        ]
    }


def test_exact_date_infers_the_only_corpus_year(
    catalog: MetadataCatalog,
) -> None:
    assert parse_where("Incendios del 13 de julio", catalog) == {
        "report_date_number": 20260713
    }


def test_date_range(catalog: MetadataCatalog) -> None:
    assert parse_where(
        "Incendios entre el 12 y el 15 de julio",
        catalog,
    ) == {
        "$and": [
            {"report_date_number": {"$gte": 20260712}},
            {"report_date_number": {"$lte": 20260715}},
        ]
    }


def test_strict_date_comparisons(catalog: MetadataCatalog) -> None:
    assert parse_where("Incendios después del 13 de julio", catalog) == {
        "report_date_number": {"$gte": 20260714}
    }
    assert parse_where("Incendios antes del 13 de julio", catalog) == {
        "report_date_number": {"$lte": 20260712}
    }
    assert parse_where("Incendios a partir del 13 de julio", catalog) == {
        "report_date_number": {"$gte": 20260713}
    }


def test_contradiction_is_reported(catalog: MetadataCatalog) -> None:
    parsed = parse_metadata_filters(
        "Incendios de León, pero no de León",
        catalog,
    )

    assert parsed.ambiguities
    with pytest.raises(ValueError, match="incluidos y excluidos"):
        build_chroma_where(parsed.filters)


def test_no_detected_filter_returns_none(catalog: MetadataCatalog) -> None:
    parsed = parse_metadata_filters(
        "Incendios con un gran despliegue de medios aéreos",
        catalog,
    )

    assert parsed.ambiguities == []
    assert build_chroma_where(parsed.filters) is None


def test_builder_rejects_inverted_date_range() -> None:
    filters = MetadataFilters(
        report_date_from=20260715,
        report_date_to=20260712,
    )

    with pytest.raises(ValueError, match="fecha inicial"):
        build_chroma_where(filters)
