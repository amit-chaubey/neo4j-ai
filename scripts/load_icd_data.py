import csv
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.database.neo4j_client import Neo4jICD
from dotenv import load_dotenv

load_dotenv()

def process_icd_row(row):
    """Process a row from the CSV into structured data"""
    return {
        'category_code': row[0],
        'subcategory': row[1],
        'full_code': row[2],
        'short_description': row[3],
        'long_description': row[4],
        'category_name': row[5]
    }

def load_icd_data():
    # Get the correct path to data/codes.csv
    current_dir = Path(__file__).parent
    csv_path = current_dir.parent / 'data' / 'codes.csv'

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    neo4j_client = Neo4jICD(
        uri=os.getenv('NEO4J_URI'),
        user=os.getenv('NEO4J_USER'),
        password=os.getenv('NEO4J_PASSWORD')
    )

    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            # Count total rows for progress reporting
            total_rows = sum(1 for _ in file)
            file.seek(0)  # Reset file pointer to start
            
            print(f"Found {total_rows} rows to process")
            processed = 0
            errors = 0

            for row in csv_reader:
                try:
                    processed_row = process_icd_row(row)
                    neo4j_client.create_icd_relationships(processed_row)
                    processed += 1
                    if processed % 100 == 0:  # Progress update every 100 rows
                        print(f"Processed {processed} rows...")
                except Exception as row_error:
                    errors += 1
                    print(f"Error processing row {processed + errors}: {str(row_error)}")
                    continue
            
            print(f"\nImport completed!")
            print(f"Successfully processed: {processed} rows")
            if errors > 0:
                print(f"Errors encountered: {errors} rows")
    
    except Exception as e:
        print(f"Fatal error during data loading: {str(e)}")
    finally:
        neo4j_client.close()

if __name__ == "__main__":
    load_icd_data()