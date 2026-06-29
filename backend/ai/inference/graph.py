import json
from pathlib import Path

from ai.config import settings
from ai.utils.lazy_imports import optional_import


class FraudGraphPipeline:
    def __init__(self, path: Path | None = None):
        self.path = path or settings.datasets_dir / "fraud_network.json"
        self.nx = optional_import("networkx")
        self.graph = None

    def load(self):
        if self.graph is not None:
            return self.graph
        payload = json.loads(self.path.read_text()) if self.path.exists() else {"nodes": [], "edges": []}
        if self.nx:
            graph = self.nx.Graph()
            graph.add_nodes_from((n["id"], n) for n in payload["nodes"])
            graph.add_edges_from((e["source"], e["target"], e) for e in payload["edges"])
            self.graph = graph
        else:
            self.graph = payload
        return self.graph

    def analyze(self) -> dict:
        graph = self.load()
        if not self.nx:
            return {**graph, "communities": [], "high_risk_nodes": []}
        pagerank = self.nx.pagerank(graph) if graph.number_of_nodes() else {}
        degree = self.nx.degree_centrality(graph) if graph.number_of_nodes() > 1 else {}
        communities = list(self.nx.algorithms.community.greedy_modularity_communities(graph)) if graph.number_of_edges() else []
        nodes = [{**data, "id": node, "pagerank": round(pagerank.get(node, 0), 6), "centrality": round(degree.get(node, 0), 6)} for node, data in graph.nodes(data=True)]
        edges = [{"source": a, "target": b, **data} for a, b, data in graph.edges(data=True)]
        high_risk = sorted(nodes, key=lambda n: n.get("risk_score", 0) + n["centrality"] * 100, reverse=True)[:50]
        return {"nodes": nodes, "edges": edges, "communities": [list(x) for x in communities], "high_risk_nodes": high_risk, "statistics": {"nodes": len(nodes), "edges": len(edges), "clusters": len(communities)}}

    def shortest_path(self, source: str, target: str) -> list[str]:
        graph = self.load()
        if not self.nx:
            return []
        try:
            return self.nx.shortest_path(graph, source, target)
        except (self.nx.NetworkXNoPath, self.nx.NodeNotFound):
            return []
