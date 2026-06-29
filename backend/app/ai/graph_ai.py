class GraphAIService:
    async def predict_cluster_risk(self, graph: dict) -> dict:
        return {"risk_score": min(len(graph.get("edges", [])) * 5, 100), "model": "graph-rules-v1"}
