from pydantic import BaseModel


class Hit(BaseModel):
    id: str
    filename: str
    path: str
    dir_id: str
    dir_name: str = ""
    snippet: str = ""
    modified: str = ""
    size: int = 0
    extension: str = ""
    score: float = 0.0


class SearchFacets(BaseModel):
    types: dict[str, int] = {}
    dirs: dict[str, dict] = {}


class SearchResponse(BaseModel):
    total: int = 0
    page: int = 1
    size: int = 20
    took_ms: int = 0
    hits: list[Hit] = []
    facets: SearchFacets = SearchFacets()


class SuggestResponse(BaseModel):
    suggestions: list[str] = []
    took_ms: int = 0


class PreviewResponse(BaseModel):
    id: str
    content: str = ""
    char_count: int = 0
    ocr_used: bool = False
    pages: int = 0


class ContentResponse(BaseModel):
    id: str
    content: str = ""
    char_count: int = 0
    ocr_used: bool = False
