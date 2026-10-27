"""Agent tools (A1): corpus search, clause lookup by identifier, request-field lookup."""
from ecs.retrieval import Index


class Toolbox:
    def __init__(self, index: Index, request: dict):
        self.index, self.request = index, request

    def search_corpus(self, query, types=None, k=5, chapters=None):
        return self.index.search(query, k=k, types=types, chapters=chapters)

    def get_clause(self, clause_id):
        c = self.index.get(clause_id)
        return [c] if c else []

    def get_request_field(self, name):
        return [{"id": f"REQ.{name}", "text": str(self.request.get(name)), "type": "request", "chapter": "-", "score": None, "coverage": None}] \
            if name in self.request else []

    TOOLS = ("search_corpus", "get_clause", "get_request_field")
