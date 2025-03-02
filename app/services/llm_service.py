from typing import List, Dict, Optional
from app.services.icd_service import ICDService
import openai
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class MedicalCodingAssistant:
    def __init__(self, icd_service: ICDService):
        self.icd_service = icd_service
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        self.base_prompt = """You are a medical coding assistant specialized in ICD-10 codes. 
        Given a medical description, suggest the most appropriate ICD-10 codes and explain your reasoning.
        
        For example:
        - If patient has Type 2 diabetes with nephropathy, suggest E11.21
        - For viral pneumonia, consider codes from J12 category
        - Always explain why you chose specific codes
        
        Use the provided database results to ensure accuracy."""

    def process_query(self, user_query: str) -> Dict:
        try:
            logger.info(f"Processing query: {user_query}")
            
            # Search in Neo4j
            db_results = self.icd_service.search_by_description(user_query)
            logger.info(f"Found {len(db_results)} results in database")
            
            if not db_results:
                return {
                    "suggested_codes": [],
                    "explanation": "I couldn't find any matching ICD-10 codes in the database. Please try rephrasing your query or provide more specific medical terms.",
                    "source": "no results"
                }
            
            # Prepare context with strict verification
            context = self._prepare_context(db_results)
            
            system_prompt = """You are a medical coding assistant specialized in ICD-10 codes. 
            IMPORTANT RULES:
            1. ONLY suggest codes that are present in the provided database results
            2. DO NOT make up or suggest codes that aren't in the database results
            3. If you're not sure about a code, say so
            4. Explain why each suggested code is relevant
            5. If the database results don't match the query well, acknowledge this
            
            Current database results:
            {context}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt.format(context=context)},
                        {"role": "user", "content": user_query}
                    ],
                    temperature=0.3  # Lower temperature for more conservative responses
                )
                
                explanation = response.choices[0].message.content
                
                return {
                    "suggested_codes": db_results,
                    "explanation": explanation,
                    "source": "database + llm",
                    "verified_codes": True
                }
                
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                return {
                    "suggested_codes": db_results,
                    "explanation": "Here are the relevant codes found in our database. For detailed explanations, please consult official ICD-10 documentation.",
                    "source": "database only",
                    "verified_codes": True
                }
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "suggested_codes": [],
                "explanation": "I apologize, but I encountered an error processing your request. Please try again.",
                "source": "error",
                "verified_codes": False
            }

    def _prepare_context(self, db_results: List[Dict]) -> str:
        """Prepare context from database results for LLM"""
        if not db_results:
            return "No exact matches found in the database."
        
        context = "Related codes found in database:\n"
        for result in db_results:
            context += f"- {result['code']}: {result['short_desc']}\n  Long description: {result['long_desc']}\n"
        
        return context 