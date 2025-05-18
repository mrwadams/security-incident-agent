"""
Security Incidents Database Setup Script

This script creates the security_incidents table in PostgreSQL and populates it with sample data.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "security")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_SCHEMA = os.environ.get("DB_SCHEMA", "public")

# Create connection string
connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_database():
    """Create the security incidents table."""
    print("Connecting to PostgreSQL database...")
    engine = create_engine(connection_string)
    
    with engine.connect() as connection:
        # Create schema if it doesn't exist
        # Quote schema name for safety if it contains special characters or needs case preservation.
        # CREATE SCHEMA IF NOT EXISTS is idempotent.
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DB_SCHEMA}"'))
        connection.commit() # Essential for DDL statements if not in autocommit mode
        print(f"Schema '{DB_SCHEMA}' ensured.")

        # Set search_path for the current session to ensure objects are created in the correct schema
        # This is important if the default search_path of the user doesn't include DB_SCHEMA first.
        connection.execute(text(f'SET search_path TO "{DB_SCHEMA}", public'))
        connection.commit()
        print(f"Search path set to '{DB_SCHEMA}'.")

        # Create security_incidents table within the specified schema
        # Note: Table name will be schema-qualified by PostgreSQL if search_path is set correctly.
        # Alternatively, explicitly qualify: f'CREATE TABLE IF NOT EXISTS "{DB_SCHEMA}".security_incidents (...'
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS security_incidents (
            incident_id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
            affected_systems TEXT,
            reported_by TEXT NOT NULL,
            assigned_to TEXT,
            resolution_notes TEXT
        );
        
        -- Add index on timestamp for time-based queries
        CREATE INDEX IF NOT EXISTS idx_security_incidents_timestamp ON security_incidents(timestamp);
        
        -- Add index on severity for filtering by severity
        CREATE INDEX IF NOT EXISTS idx_security_incidents_severity ON security_incidents(severity);
        
        -- Add index on category for filtering by category
        CREATE INDEX IF NOT EXISTS idx_security_incidents_category ON security_incidents(category);
        
        -- Add index on status for filtering by status
        CREATE INDEX IF NOT EXISTS idx_security_incidents_status ON security_incidents(status);
        """
    
        connection.execute(text(create_table_sql))
        connection.commit()
    
    print(f"Security incidents table created successfully in schema '{DB_SCHEMA}'")
    
    return engine

def generate_sample_data():
    """Generate sample security incident data."""
    print("Generating sample security incident data...")
    
    # Sample data parameters
    num_incidents = 200
    current_date = datetime.now()
    start_date = current_date - timedelta(days=180)  # 6 months ago
    
    # Sample data lists
    severities = ['Low', 'Medium', 'High', 'Critical']
    categories = [
        'Phishing', 'Malware', 'Unauthorized Access', 'Data Breach', 
        'DDoS Attack', 'Insider Threat', 'Social Engineering', 
        'Password Attack', 'Man-in-the-Middle', 'Ransomware'
    ]
    statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
    systems = [
        'Email Server', 'Web Application', 'Database Server', 'File Server', 
        'Active Directory', 'Network Infrastructure', 'Cloud Services', 
        'Endpoint Devices', 'Mobile Devices', 'IoT Devices'
    ]
    departments = ['IT', 'Finance', 'HR', 'Marketing', 'Sales', 'Operations', 'R&D', 'Legal']
    
    employees = {
        'IT': ['John Smith', 'Emma Johnson', 'Michael Chen', 'Sarah Williams'],
        'Security': ['David Rodriguez', 'Lisa Patel', 'Omar Hassan', 'Kelly Morris'],
        'Finance': ['Robert Taylor', 'Jessica Lee', 'Thomas Brown', 'Amanda Clark'],
        'HR': ['James Wilson', 'Samantha Davis', 'Christopher Martin', 'Elizabeth Thompson'],
        'Marketing': ['Daniel White', 'Olivia Garcia', 'Andrew Miller', 'Sophia Moore'],
        'Sales': ['Matthew Jackson', 'Emily Martinez', 'Ryan Anderson', 'Jennifer Lewis'],
        'Operations': ['William Harris', 'Nicole Robinson', 'Benjamin Scott', 'Rebecca Allen'],
        'R&D': ['Joseph Hill', 'Stephanie Green', 'Brian Baker', 'Michelle Adams'],
        'Legal': ['Kevin Nelson', 'Laura Phillips', 'Tyler Evans', 'Victoria Wright']
    }
    
    # Generate incidents
    incidents = []
    for i in range(1, num_incidents + 1):
        # Random date within the last 6 months, weighted toward more recent
        days_ago = int(random.expovariate(1/30)) % 180  # Exponential distribution, capped at 180 days
        incident_date = current_date - timedelta(days=days_ago)
        
        # Select random values from lists
        severity = random.choices(severities, weights=[0.4, 0.3, 0.2, 0.1])[0]
        category = random.choice(categories)
        status = random.choice(statuses) if days_ago > 7 else random.choice(['Open', 'In Progress'])
        
        # Affected systems - random selection of 1-3 systems
        num_systems = random.randint(1, 3)
        affected = ', '.join(random.sample(systems, num_systems))
        
        # Reporting department and reporter
        reporting_dept = random.choice(departments)
        reporter = random.choice(employees[reporting_dept])
        
        # Assigned to security team member
        assigned_to = random.choice(employees['Security'])
        
        # Description and resolution notes
        description = f"{severity} {category} incident affecting {affected} in the {reporting_dept} department."
        resolution_notes = None
        if status in ['Resolved', 'Closed']:
            resolution_notes = f"Issue resolved by {assigned_to}. Mitigation measures implemented."
        
        # Add incident to list
        incidents.append({
            'incident_id': i,
            'timestamp': incident_date,
            'severity': severity,
            'category': category,
            'description': description,
            'status': status,
            'affected_systems': affected,
            'reported_by': reporter,
            'assigned_to': assigned_to,
            'resolution_notes': resolution_notes
        })
    
    # Convert to DataFrame
    df = pd.DataFrame(incidents)
    return df

def insert_sample_data(engine, df):
    """Insert sample data into the security_incidents table."""
    print(f"Inserting sample data into the database (schema: '{DB_SCHEMA}')...")
    
    # Check if table already has data within the specified schema
    with engine.connect() as connection:
        # Ensure the search path is set for this connection as well,
        # or explicitly qualify the table name in the query.
        connection.execute(text(f'SET search_path TO "{DB_SCHEMA}", public'))
        # Query to count records in the specific schema's table
        # The table name 'security_incidents' will be resolved using the search_path.
        # Alternatively, use f'SELECT COUNT(*) FROM "{DB_SCHEMA}".security_incidents'
        result = connection.execute(text("SELECT COUNT(*) FROM security_incidents"))
        count = result.scalar_one() # Use scalar_one() or scalar()
    
    if count > 0:
        print(f"Table 'security_incidents' in schema '{DB_SCHEMA}' already contains {count} records. Skipping sample data insertion.")
        return
    
    # Insert data into database, specifying the schema for the table
    # The to_sql method's schema parameter handles this.
    df.to_sql('security_incidents', engine, schema=DB_SCHEMA, if_exists='append', index=False)
    print(f"Successfully inserted {len(df)} sample security incidents into schema '{DB_SCHEMA}'")

def main():
    # Create database and table
    engine = create_database()
    
    # Generate and insert sample data
    df = generate_sample_data()
    insert_sample_data(engine, df)
    
    print("Database setup complete!")

if __name__ == "__main__":
    main()