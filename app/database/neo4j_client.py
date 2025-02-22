from neo4j import GraphDatabase
import logging

class Neo4jICD:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def create_icd_relationships(self, row):
        with self._driver.session() as session:
            # Create nodes and relationships for one ICD code entry
            query = """
            MERGE (cat:Category {name: $category_name})
            
            MERGE (code:ICDCode {
                code: $full_code,
                category_code: $category_code,
                subcategory: $subcategory,
                short_desc: $short_description,
                long_desc: $long_description
            })
            
            MERGE (cat)-[:CONTAINS]->(code)
            
            // Create hierarchical relationships
            WITH cat, code
            MATCH (parent:ICDCode)
            WHERE parent.code = $category_code
            MERGE (parent)-[:HAS_SUBCATEGORY]->(code)
            """
            
            session.run(query, 
                category_name=row['category_name'],
                full_code=row['full_code'],
                category_code=row['category_code'],
                subcategory=row['subcategory'],
                short_description=row['short_description'],
                long_description=row['long_description']
            )

    def get_disease_info(self, icd_code):
        with self._driver.session() as session:
            query = """
            MATCH (code:ICDCode {code: $code})
            OPTIONAL MATCH (code)<-[:HAS_SUBCATEGORY]-(parent:ICDCode)
            OPTIONAL MATCH (code)-[:HAS_SUBCATEGORY]->(child:ICDCode)
            RETURN 
                code.long_desc as description,
                code.category_code as category,
                collect(DISTINCT parent.code) as parent_codes,
                collect(DISTINCT child.code) as child_codes
            """
            return session.run(query, code=icd_code).single()