from app.database.neo4j_client import Neo4jICD
from app.models.icd_models import ICDCode, ICDResponse
from typing import Optional, List
from neo4j import GraphDatabase

class ICDService:
    def __init__(self, neo4j_client: Neo4jICD):
        self.db_client = neo4j_client
        self.driver = GraphDatabase.driver(neo4j_client.uri, auth=(neo4j_client.user, neo4j_client.password))

    def create_icd_code(self, icd_code: ICDCode) -> None:
        """Create ICD code and its relationships in Neo4j"""
        row = icd_code.model_dump()
        self.db_client.create_icd_relationships(row)

    def get_disease_info(self, code: str) -> Optional[ICDResponse]:
        """Get disease information including related conditions"""
        result = self.db_client.get_disease_info(code)
        
        if not result:
            return None

        return ICDResponse(
            code=code,
            description=result["description"],
            category=result["category"],
            related_conditions=result["parent_codes"] + result["child_codes"]
        )

    def close(self):
        self.driver.close()

    def search_by_description(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search ICD codes by matching description
        """
        with self.driver.session() as session:
            cypher_query = """
            MATCH (code:ICDCode)
            WHERE code.short_desc CONTAINS $query OR code.long_desc CONTAINS $query
            RETURN code
            LIMIT $limit
            """
            result = session.run(cypher_query, query=query.upper(), limit=limit)
            return [record["code"] for record in result]

    def get_category_codes(self, category_code: str) -> List[dict]:
        """
        Get all ICD codes within a specific category
        """
        with self.driver.session() as session:
            cypher_query = """
            MATCH (cat:Category)<-[:BELONGS_TO]-(code:ICDCode)
            WHERE code.category_code = $category_code
            RETURN code
            ORDER BY code.code
            """
            result = session.run(cypher_query, category_code=category_code)
            return [record["code"] for record in result]

    def get_code_details(self, code: str) -> Optional[dict]:
        """
        Get detailed information about a specific ICD code
        """
        with self.driver.session() as session:
            cypher_query = """
            MATCH (code:ICDCode {code: $code})
            OPTIONAL MATCH (code)-[:BELONGS_TO]->(category:Category)
            RETURN code, category
            """
            result = session.run(cypher_query, code=code)
            record = result.single()
            if record:
                details = record["code"]
                if record["category"]:
                    details["category_name"] = record["category"]["name"]
                return details
            return None
