from app.database.neo4j_client import Neo4jICD
from app.models.icd_models import ICDCode, ICDResponse
from typing import Optional, List
from neo4j import GraphDatabase
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ICDService:
    def __init__(self, uri: str, user: str, password: str):
        logger.info(f"Initializing ICDService with URI: {uri}")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._verify_connection()

    def _verify_connection(self):
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()["count"]
                logger.info(f"Connected to Neo4j. Total nodes: {count}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

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

    def _extract_medical_terms(self, query: str) -> List[str]:
        """Extract medical terms with context"""
        query = re.sub(r'[^\w\s]', ' ', query.lower())
        
        # Medical term mappings with hierarchical context
        medical_mappings = {
            'typhoid': ['typhoid', 'a01', 'fever'],
            'pneumonia': ['pneumonia', 'j12', 'respiratory'],
            'fever': ['fever', 'temperature'],
            'respiratory': ['respiratory', 'breathing'],
            'infection': ['infection', 'infectious'],
            'viral': ['viral', 'virus']
        }
        
        words = query.split()
        expanded_terms = set()
        
        # Process multi-word terms
        for i in range(len(words)-1):
            two_words = f"{words[i]} {words[i+1]}"
            if two_words in medical_mappings:
                expanded_terms.update(medical_mappings[two_words])
        
        # Process single words
        for word in words:
            if word in medical_mappings:
                expanded_terms.update(medical_mappings[word])
            elif len(word) > 2:
                expanded_terms.add(word)
        
        logger.info(f"Expanded medical terms: {expanded_terms}")
        return list(expanded_terms)

    def _normalize_code(self, code: str) -> str:
        """Normalize ICD code by removing dots"""
        return code.replace(".", "")

    def search_by_description(self, search_text: str, limit: int = 10) -> List[dict]:
        """
        Search using Neo4j graph structure and relationships
        """
        logger.info(f"Searching for: {search_text}")
        
        search_terms = self._extract_medical_terms(search_text)
        logger.info(f"Extracted terms: {search_terms}")
        
        with self.driver.session() as session:
            cypher_query = """
            // Match codes based on search terms
            MATCH (code:ICDCode)
            WHERE code.code = $search_text
                OR ANY(term IN $search_terms WHERE
                    toLower(code.code) CONTAINS toLower(term)
                    OR toLower(code.short_desc) CONTAINS toLower(term)
                )

            // Convert node properties to dictionary in Neo4j
            WITH {
                code: code.code,
                short_desc: code.short_desc,
                long_desc: code.long_desc,
                category_code: code.category_code
            } as result,
            CASE 
                WHEN code.code = $search_text THEN 100
                WHEN code.short_desc CONTAINS toLower($search_text) THEN 75
                ELSE 50
            END as relevance

            RETURN result, relevance
            ORDER BY relevance DESC, result.code
            LIMIT $limit
            """
            
            try:
                result = session.run(
                    cypher_query,
                    search_text=search_text.upper(),
                    search_terms=search_terms,
                    limit=limit
                )
                
                codes = []
                for record in result:
                    # Get the already-converted dictionary
                    code_data = record["result"]
                    
                    # Format code with dot notation if needed
                    if len(code_data['code']) > 3:
                        formatted_code = f"{code_data['code'][:3]}.{code_data['code'][3:]}"
                    else:
                        formatted_code = code_data['code']
                    
                    # Create new dictionary with formatted code
                    formatted_data = {
                        'code': formatted_code,
                        'short_desc': code_data['short_desc'],
                        'long_desc': code_data['long_desc'],
                        'category_code': code_data['category_code']
                    }
                    
                    codes.append(formatted_data)
                    logger.info(f"Found code {formatted_data['code']} ({formatted_data['short_desc']})")
                
                return codes
                
            except Exception as e:
                logger.error(f"Neo4j query failed: {str(e)}")
                logger.error(f"Search text: {search_text}")
                logger.error(f"Search terms: {search_terms}")
                return []

    def get_category_codes(self, category_code: str) -> List[dict]:
        """Get all codes in a category with their relationships"""
        with self.driver.session() as session:
            cypher_query = """
            MATCH (category:Category {code: $category_code})<-[:BELONGS_TO]-(code:ICDCode)
            OPTIONAL MATCH (code)-[:IS_A]->(parent:ICDCode)
            RETURN {
                code: code.code,
                short_desc: code.short_desc,
                long_desc: code.long_desc,
                parent_code: COALESCE(parent.code, ''),
                parent_desc: COALESCE(parent.short_desc, '')
            } as code_info
            ORDER BY code_info.code
            """
            
            try:
                result = session.run(cypher_query, category_code=category_code)
                return [record["code_info"] for record in result]
            except Exception as e:
                logger.error(f"Neo4j query failed: {str(e)}")
                return []

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
