from app.database.neo4j_client import Neo4jICD
from app.models.icd_models import ICDCode, ICDResponse
from typing import Optional, List
from neo4j import GraphDatabase

class ICDService:
    def __init__(self, uri: str, user: str, password: str):
        """Initialize the ICDService with Neo4j connection details"""
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

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
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()

    def search_by_description(self, query: str, limit: int = 10) -> List[dict]:
        """
        Enhanced search for ICD codes with multiple search strategies
        """
        with self.driver.session() as session:
            # Clean and prepare the search term
            search_term = query.strip().upper()
            
            cypher_query = """
            MATCH (code:ICDCode)
            WHERE 
                // Code exact or partial match
                code.code CONTAINS $search_term
                // Description matches (case insensitive)
                OR toUpper(code.short_desc) CONTAINS $search_term
                OR toUpper(code.long_desc) CONTAINS $search_term
                // Category code match
                OR code.category_code CONTAINS $search_term
            RETURN DISTINCT code
            ORDER BY 
                // Exact matches first
                CASE 
                    WHEN code.code = $search_term THEN 0
                    WHEN code.category_code = $search_term THEN 1
                    ELSE 2 
                END,
                code.code
            LIMIT $limit
            """
            
            result = session.run(cypher_query, 
                               search_term=search_term,
                               limit=limit)
            return [record["code"] for record in result]

    def get_category_codes(self, category_code: str) -> List[dict]:
        """
        Get all ICD codes within a specific category with improved matching
        """
        with self.driver.session() as session:
            # Clean and prepare the category code
            search_term = category_code.strip().upper()
            
            cypher_query = """
            MATCH (code:ICDCode)
            WHERE 
                // Match exact category or starts with the category
                code.category_code = $search_term
                OR code.code STARTS WITH $search_term
            RETURN code
            ORDER BY code.code
            """
            
            result = session.run(cypher_query, search_term=search_term)
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
