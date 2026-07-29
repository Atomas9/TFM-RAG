import ollama
import json

from revisor_query_filters import FilterReview
from query_filters import DeterministicAnalysis, MetadataCatalog

from typing import Literal
from pydantic import BaseModel, Field

OLLAMA_MODEL = 'gemma4:31b-cloud'
SYSTEM_PROMPT = '''

'''.strip()

USER_PROMPT = '''

'''.strip()

FilterField = Literal[
    "country",
    "autonomous_community_normalized",
    "province_normalized",
    "location_normalized",
    "status",
    "operational_status",
    "report_date_number",
]

FilterOperator = Literal[
    "eq",
    "ne",
    "in",
    "nin",
    "gte",
    "lte",
]


class FilterCondition(BaseModel):
    field: FilterField
    operator: FilterOperator
    value: str | int | list[str] | list[int]


class FilterGroup(BaseModel):
    logic: Literal["and", "or"]
    conditions: list[FilterCondition] = Field(
        min_length=1
    )


class FilterProposal(BaseModel):
    groups: list[FilterGroup] = Field(
        default_factory=list
    )
    explanation: str

def generate_filter_llm(
        query: str, 
        analysis: DeterministicAnalysis,
        review: FilterReview,
        catalog: MetadataCatalog,
        model_name: str = OLLAMA_MODEL
) -> FilterProposal:
    if not query.strip():
        raise ValueError('La pregunta no puede estar vacía')
    
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': USER_PROMPT.format(

            )
        }
    ]

    response = ollama.chat(
        model = model_name,
        messages = messages,
        format = FilterProposal.model_json_schema(),
        options = {
            'temperature': 0,
        }
    )

    proposal = FilterProposal.model_validate_json(
        response.message.content
    )
    
    
    return proposal