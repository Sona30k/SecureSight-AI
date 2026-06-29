from typing import Any

from neo4j import AsyncGraphDatabase

from app.config.settings import settings


class Neo4jClient:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )

    async def close(self) -> None:
        await self.driver.close()

    async def verify(self) -> bool:
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def create_report(self, report: dict[str, Any]) -> dict:
        query = """
        MERGE (c:Citizen {name: $citizen})
        MERGE (r:Complaint {case_id: $case_id})
        SET r.risk_score = $risk_score, r.updated_at = datetime()
        MERGE (c)-[:APPEARED_IN]->(r)
        WITH c, r
        UNWIND $phones AS value MERGE (n:Phone {value: value}) MERGE (n)-[:CALLED]->(c) MERGE (n)-[:APPEARED_IN]->(r)
        WITH c, r
        UNWIND $devices AS value MERGE (n:Device {value: value}) MERGE (c)-[:HAS_DEVICE]->(n) MERGE (n)-[:APPEARED_IN]->(r)
        WITH c, r
        UNWIND $bank_accounts AS value MERGE (n:BankAccount {value: value}) MERGE (c)-[:TRANSFERRED]->(n) MERGE (n)-[:APPEARED_IN]->(r)
        WITH c, r
        UNWIND $upi_ids AS value MERGE (n:UPI {value: value}) MERGE (c)-[:USES]->(n) MERGE (n)-[:APPEARED_IN]->(r)
        RETURN r.case_id AS case_id
        """
        async with self.driver.session() as session:
            record = await session.execute_write(lambda tx: tx.run(query, **report))
            summary = await record.single()
            return {"case_id": summary["case_id"], "status": "created"}

    async def network(self, case_id: str) -> dict:
        query = """
        MATCH (r:Complaint {case_id:$case_id})<-[:APPEARED_IN]-(n)
        OPTIONAL MATCH (n)-[rel]-(other)
        RETURN collect(DISTINCT {id:elementId(n), label:labels(n)[0], data:properties(n)}) AS nodes,
               collect(DISTINCT {source:elementId(n), target:elementId(other), type:type(rel)}) AS edges
        """
        async with self.driver.session() as session:
            result = await session.run(query, case_id=case_id)
            row = await result.single()
            return {"case_id": case_id, "nodes": row["nodes"] if row else [], "edges": row["edges"] if row else []}

    async def high_risk(self, minimum: int = 70) -> list[dict]:
        async with self.driver.session() as session:
            result = await session.run(
                "MATCH (r:Complaint) WHERE r.risk_score >= $minimum RETURN r ORDER BY r.risk_score DESC LIMIT 100",
                minimum=minimum,
            )
            return [dict(row["r"]) async for row in result]
