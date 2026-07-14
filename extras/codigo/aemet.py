from __future__ import annotations

import hashlib
import json
import os
import tarfile
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv
from lxml import etree


load_dotenv()


AEMET_API_KEY = os.getenv("AEMET_API_KEY")

if not AEMET_API_KEY:
    raise RuntimeError(
        "No se ha encontrado AEMET_API_KEY. "
        "Define la variable en un archivo .env o en el entorno."
    )


BASE_URL = "https://opendata.aemet.es/opendata/api"

# Avisos CAP último elaborado para toda España.
# También puedes cambiar "esp" por una comunidad/provincia/zona si lo necesitáis.
AEMET_WARNINGS_ENDPOINT = f"{BASE_URL}/avisos_cap/ultimoelaborado/area/esp"

OUTPUT_DIR = Path("data/aemet")
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AemetRawDownload:
    endpoint: str
    datos_url: str
    metadatos_url: Optional[str]
    local_path: str
    sha256: str
    content_type: str
    fetched_at: str


@dataclass
class RagDocument:
    text: str
    metadata: dict[str, Any]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fix_text_encoding(value: Any) -> Any:
    """
    Corrige casos tipo 'Temperaturas mÃ¡ximas' cuando aparecen problemas
    de codificación. Si no hay problema, devuelve el texto original.
    """
    if not isinstance(value, str):
        return value

    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def recursively_fix_encoding(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: recursively_fix_encoding(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [recursively_fix_encoding(v) for v in obj]
    return fix_text_encoding(obj)


def request_aemet_endpoint(endpoint: str) -> dict[str, Any]:
    """
    Primera llamada a AEMET OpenData.

    AEMET no devuelve directamente el recurso final, sino un JSON de envoltorio:
    {
        "descripcion": "exito",
        "estado": 200,
        "datos": "https://opendata.aemet.es/opendata/sh/...",
        "metadatos": "https://opendata.aemet.es/opendata/sh/..."
    }
    """
    headers = {
        "Accept": "application/json",
        "api_key": AEMET_API_KEY,
        "User-Agent": "TFM-RAG-Incendios/1.0 contacto: tu_email@ejemplo.com",
    }

    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(endpoint)
        response.raise_for_status()

    payload = response.json()

    estado = payload.get("estado")
    if estado != 200:
        raise RuntimeError(f"AEMET devolvió estado no exitoso: {payload}")

    if "datos" not in payload:
        raise RuntimeError(f"La respuesta de AEMET no contiene campo 'datos': {payload}")

    return payload


def download_aemet_data(datos_url: str) -> tuple[bytes, str]:
    """
    Segunda llamada: descarga el recurso real desde la URL temporal del campo 'datos'.
    """
    headers = {
        "User-Agent": "TFM-RAG-Incendios/1.0 contacto: tu_email@ejemplo.com",
    }

    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        response = client.get(datos_url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    return response.content, content_type


def save_raw_resource(
    endpoint: str,
    datos_url: str,
    metadatos_url: Optional[str],
    content: bytes,
    content_type: str,
) -> AemetRawDownload:
    digest = sha256_bytes(content)
    fetched_at = now_utc_iso()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    extension = guess_extension(content, content_type)

    raw_path = RAW_DIR / f"{timestamp}_aemet_{digest[:12]}{extension}"
    raw_path.write_bytes(content)

    raw_download = AemetRawDownload(
        endpoint=endpoint,
        datos_url=datos_url,
        metadatos_url=metadatos_url,
        local_path=str(raw_path),
        sha256=digest,
        content_type=content_type,
        fetched_at=fetched_at,
    )

    return raw_download


def guess_extension(content: bytes, content_type: str) -> str:
    ct = content_type.lower()

    if content.startswith(b"{") or "json" in ct or "geo+json" in ct:
        return ".json"

    if content.startswith(b"<?xml") or content.startswith(b"<") or "xml" in ct:
        return ".xml"

    if zipfile.is_zipfile(BytesIO(content)):
        return ".zip"

    if tarfile.is_tarfile(fileobj := BytesIO(content)):
        return ".tar"

    if "gzip" in ct or content[:2] == b"\x1f\x8b":
        return ".gz"

    return ".bin"


def parse_downloaded_resource(content: bytes, content_type: str) -> list[RagDocument]:
    """
    AEMET puede devolver distintos formatos según el producto:
    - GeoJSON/JSON
    - XML CAP
    - TAR/ZIP con varios XML CAP
    """
    fixed_content_type = content_type.lower()

    if zipfile.is_zipfile(BytesIO(content)):
        return parse_zip_cap_files(content)

    if tarfile.is_tarfile(BytesIO(content)):
        return parse_tar_cap_files(content)

    stripped = content.lstrip()

    if stripped.startswith(b"{") or "json" in fixed_content_type or "geo+json" in fixed_content_type:
        data = json.loads(content.decode("utf-8", errors="replace"))
        data = recursively_fix_encoding(data)

        if data.get("type") == "FeatureCollection":
            return geojson_to_rag_documents(data)

        return generic_json_to_rag_documents(data)

    if stripped.startswith(b"<") or "xml" in fixed_content_type:
        return cap_xml_to_rag_documents(content)

    raise ValueError(
        f"No sé parsear este recurso. Content-Type={content_type}, "
        f"primeros bytes={content[:40]!r}"
    )


def parse_zip_cap_files(content: bytes) -> list[RagDocument]:
    docs: list[RagDocument] = []

    with zipfile.ZipFile(BytesIO(content)) as z:
        for name in z.namelist():
            if not name.lower().endswith(".xml"):
                continue

            xml_bytes = z.read(name)
            file_docs = cap_xml_to_rag_documents(xml_bytes)

            for doc in file_docs:
                doc.metadata["source_file"] = name

            docs.extend(file_docs)

    return docs


def parse_tar_cap_files(content: bytes) -> list[RagDocument]:
    docs: list[RagDocument] = []

    with tarfile.open(fileobj=BytesIO(content), mode="r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            if not member.name.lower().endswith(".xml"):
                continue

            extracted = tar.extractfile(member)
            if extracted is None:
                continue

            xml_bytes = extracted.read()
            file_docs = cap_xml_to_rag_documents(xml_bytes)

            for doc in file_docs:
                doc.metadata["source_file"] = member.name

            docs.extend(file_docs)

    return docs


def geojson_to_rag_documents(geojson: dict[str, Any]) -> list[RagDocument]:
    """
    Convierte un GeoJSON de avisos en documentos RAG.

    Regla recomendada:
    1 feature = 1 documento/chunk

    Esto es mejor que partir por tokens porque cada feature ya es una unidad
    semántica completa: zona + fenómeno + severidad + vigencia + geometría.
    """
    docs: list[RagDocument] = []

    features = geojson.get("features", [])

    for i, feature in enumerate(features):
        properties = feature.get("properties", {}) or {}
        geometry = feature.get("geometry")

        zone_name = first_non_empty(
            properties,
            ["Nombre_zona", "nombre_zona", "areaDesc", "AreaDesc"],
        )

        phenomenon = first_non_empty(
            properties,
            ["ATTA", "Fenomeno", "fenomeno", "event", "Evento"],
        )

        headline = first_non_empty(
            properties,
            ["Resum_ATTA", "headline", "Headline", "titulo"],
        )

        description = first_non_empty(
            properties,
            ["Des_ATTA", "description", "Descripcion", "descripción"],
        )

        severity = first_non_empty(
            properties,
            ["Sev_ATTA", "severity", "Severity", "nivel"],
        )

        severity_level = first_non_empty(
            properties,
            ["Nivel_ATTA", "nivel", "level"],
        )

        value = first_non_empty(
            properties,
            ["Valor_ATTA", "valor", "threshold"],
        )

        probability = first_non_empty(
            properties,
            ["Prb_ATTA", "probability", "Probabilidad"],
        )

        certainty = first_non_empty(
            properties,
            ["Cer_ATTA", "certainty", "Certeza"],
        )

        valid_from = first_non_empty(
            properties,
            ["Onset_ATTA", "onset", "valid_from", "inicio"],
        )

        valid_to = first_non_empty(
            properties,
            ["Expire_ATTA", "expires", "valid_to", "fin"],
        )

        identifier = first_non_empty(
            properties,
            ["Identf_ATTA", "identifier", "id"],
        )

        text = build_aemet_warning_text(
            zone_name=zone_name,
            phenomenon=phenomenon,
            headline=headline,
            description=description,
            severity=severity,
            severity_level=severity_level,
            value=value,
            probability=probability,
            certainty=certainty,
            valid_from=valid_from,
            valid_to=valid_to,
        )

        metadata = {
            "source": "AEMET",
            "doc_type": "weather_warning",
            "format": "geojson",
            "chunk_strategy": "one_feature_one_document",
            "feature_index": i,
            "identifier": identifier,
            "zone_name": zone_name,
            "phenomenon": phenomenon,
            "headline": headline,
            "severity": severity,
            "severity_level": severity_level,
            "value": value,
            "probability": probability,
            "certainty": certainty,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "geometry": geometry,
            "trust": "official_high",
        }

        docs.append(RagDocument(text=text, metadata=metadata))

    return docs


def cap_xml_to_rag_documents(xml_bytes: bytes) -> list[RagDocument]:
    """
    Convierte XML CAP en documentos RAG.

    CAP puede contener varias secciones <info>, por idioma o actualización.
    Se crea un documento por cada <info>.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(xml_bytes, parser=parser)

    ns = root.nsmap.get(None)
    namespace = f"{{{ns}}}" if ns else ""

    def find_text(parent: etree._Element, tag: str) -> Optional[str]:
        elem = parent.find(f"{namespace}{tag}")
        if elem is None or elem.text is None:
            return None
        return fix_text_encoding(elem.text.strip())

    identifier = find_text(root, "identifier")
    sender = find_text(root, "sender")
    sent = find_text(root, "sent")
    status = find_text(root, "status")
    msg_type = find_text(root, "msgType")
    scope = find_text(root, "scope")

    info_elements = root.findall(f"{namespace}info")
    docs: list[RagDocument] = []

    for idx, info in enumerate(info_elements):
        language = find_text(info, "language")
        category = find_text(info, "category")
        event = find_text(info, "event")
        urgency = find_text(info, "urgency")
        severity = find_text(info, "severity")
        certainty = find_text(info, "certainty")
        effective = find_text(info, "effective")
        onset = find_text(info, "onset")
        expires = find_text(info, "expires")
        sender_name = find_text(info, "senderName")
        headline = find_text(info, "headline")
        description = find_text(info, "description")
        instruction = find_text(info, "instruction")

        area_descs = []
        polygons = []

        for area in info.findall(f"{namespace}area"):
            area_desc = find_text(area, "areaDesc")
            if area_desc:
                area_descs.append(area_desc)

            polygon = find_text(area, "polygon")
            if polygon:
                polygons.append(polygon)

        text = build_aemet_warning_text(
            zone_name=", ".join(area_descs) if area_descs else None,
            phenomenon=event,
            headline=headline,
            description=description,
            severity=severity,
            severity_level=None,
            value=None,
            probability=None,
            certainty=certainty,
            valid_from=onset or effective,
            valid_to=expires,
            instruction=instruction,
        )

        metadata = {
            "source": "AEMET",
            "doc_type": "weather_warning",
            "format": "cap_xml",
            "chunk_strategy": "one_cap_info_one_document",
            "identifier": identifier,
            "sender": sender,
            "sender_name": sender_name,
            "sent": sent,
            "status": status,
            "message_type": msg_type,
            "scope": scope,
            "info_index": idx,
            "language": language,
            "category": category,
            "phenomenon": event,
            "urgency": urgency,
            "severity": severity,
            "certainty": certainty,
            "valid_from": onset or effective,
            "valid_to": expires,
            "area_descs": area_descs,
            "polygons": polygons,
            "trust": "official_high",
        }

        docs.append(RagDocument(text=text, metadata=metadata))

    return docs


def generic_json_to_rag_documents(data: Any) -> list[RagDocument]:
    """
    Fallback para JSON que no sea GeoJSON.
    No es lo ideal, pero permite no perder datos si el endpoint devuelve
    otra estructura.
    """
    text = json.dumps(data, ensure_ascii=False, indent=2)

    return [
        RagDocument(
            text=f"Datos meteorológicos de AEMET en formato JSON:\n{text}",
            metadata={
                "source": "AEMET",
                "doc_type": "weather_data",
                "format": "json",
                "chunk_strategy": "whole_json_fallback",
                "trust": "official_high",
            },
        )
    ]


def build_aemet_warning_text(
    zone_name: Optional[str],
    phenomenon: Optional[str],
    headline: Optional[str],
    description: Optional[str],
    severity: Optional[str],
    severity_level: Optional[str],
    value: Optional[str],
    probability: Optional[str],
    certainty: Optional[str],
    valid_from: Optional[str],
    valid_to: Optional[str],
    instruction: Optional[str] = None,
) -> str:
    """
    Convierte datos estructurados en texto natural controlado.
    Este texto será lo que se embeba en el índice vectorial.
    """
    lines = [
        "Aviso meteorológico oficial de AEMET.",
    ]

    if headline:
        lines.append(f"Resumen: {headline}.")

    if zone_name:
        lines.append(f"Zona afectada: {zone_name}.")

    if phenomenon:
        lines.append(f"Fenómeno meteorológico: {phenomenon}.")

    if severity:
        lines.append(f"Nivel o severidad del aviso: {severity}.")

    if severity_level:
        lines.append(f"Nivel numérico del aviso: {severity_level}.")

    if value:
        lines.append(f"Valor previsto o umbral: {value}.")

    if probability:
        lines.append(f"Probabilidad: {probability}.")

    if certainty:
        lines.append(f"Certeza: {certainty}.")

    if valid_from or valid_to:
        lines.append(f"Vigencia: desde {valid_from or 'desconocido'} hasta {valid_to or 'desconocido'}.")

    if description:
        lines.append(f"Descripción: {description}")

    if instruction:
        lines.append(f"Instrucciones o recomendaciones del aviso: {instruction}")

    return "\n".join(lines).strip()


def first_non_empty(data: dict[str, Any], keys: list[str]) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value not in [None, ""]:
            return value
    return None


def save_rag_documents(
    docs: list[RagDocument],
    raw_download: AemetRawDownload,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = PROCESSED_DIR / f"{timestamp}_aemet_rag_documents_{raw_download.sha256[:12]}.json"

    payload = {
        "raw_download": asdict(raw_download),
        "num_documents": len(docs),
        "documents": [
            {
                "text": doc.text,
                "metadata": {
                    **doc.metadata,
                    "raw_sha256": raw_download.sha256,
                    "raw_local_path": raw_download.local_path,
                    "fetched_at": raw_download.fetched_at,
                    "aemet_datos_url": raw_download.datos_url,
                },
            }
            for doc in docs
        ],
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return output_path


def ingest_aemet_warnings() -> list[RagDocument]:
    print("[AEMET] Solicitando endpoint...")
    envelope = request_aemet_endpoint(AEMET_WARNINGS_ENDPOINT)

    datos_url = envelope["datos"]
    metadatos_url = envelope.get("metadatos")

    print(f"[AEMET] URL temporal de datos: {datos_url}")

    print("[AEMET] Descargando recurso real...")
    content, content_type = download_aemet_data(datos_url)

    raw_download = save_raw_resource(
        endpoint=AEMET_WARNINGS_ENDPOINT,
        datos_url=datos_url,
        metadatos_url=metadatos_url,
        content=content,
        content_type=content_type,
    )

    print(f"[AEMET] Recurso guardado en: {raw_download.local_path}")
    print(f"[AEMET] Content-Type: {content_type}")
    print(f"[AEMET] SHA256: {raw_download.sha256}")

    print("[AEMET] Parseando recurso...")
    docs = parse_downloaded_resource(content, content_type)

    print(f"[AEMET] Documentos RAG generados: {len(docs)}")

    processed_path = save_rag_documents(docs, raw_download)
    print(f"[AEMET] Documentos procesados guardados en: {processed_path}")

    return docs


def main() -> None:
    docs = ingest_aemet_warnings()

    print("\nEjemplo de documento RAG:\n")

    if docs:
        print("TEXT:")
        print(docs[0].text)
        print("\nMETADATA:")
        print(json.dumps(docs[0].metadata, ensure_ascii=False, indent=2))
    else:
        print("No se han generado documentos.")


if __name__ == "__main__":
    main()