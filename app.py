"""
Security Incidents AI Query Agent

This application uses Vertex AI Gemini to create an AI agent that can:
1. Understand natural language queries about security incidents
2. Convert them to SQL queries against a Postgres database
3. Execute the queries and return formatted responses

Requirements:
- Google Cloud project with Vertex AI API enabled
- Postgres database with security incidents table
- Service account with appropriate permissions
"""

import os
import json
import psycopg2
import pandas as pd
from sqlalchemy import create_engine, text
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Import the Google AI SDK
from google import genai
from google.genai import types

# Database Configuration
class DatabaseConfig:
    """Configuration for PostgreSQL database connection."""
    def __init__(
        self, 
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        schema: str  # Schema is now a required parameter
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        
    def get_connection_string(self) -> str:
        """Get SQLAlchemy connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

# Database Connector
class DatabaseConnector:
    """Connector for PostgreSQL database."""
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        
    def connect(self):
        """Create database connection, ensure schema exists, and set search_path."""
        try:
            self.engine = create_engine(
                self.config.get_connection_string(),
                connect_args={'options': f'-csearch_path={self.config.schema},public'}
            )
            
            with self.engine.connect() as connection:
                # Check if schema exists
                schema_check_query = text(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name_param"
                )
                result = connection.execute(schema_check_query, {"schema_name_param": self.config.schema})
                schema_exists = result.scalar_one_or_none() is not None
                
                if not schema_exists:
                    print(f"Schema '{self.config.schema}' not found. Attempting to create...")
                    # Quote schema name for safety if it contains special characters or needs case preservation.
                    # CREATE SCHEMA IF NOT EXISTS is idempotent.
                    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.config.schema}"' ))
                    connection.commit() # Essential for DDL statements if not in autocommit mode
                    print(f"Schema '{self.config.schema}' created successfully.")
                else:
                    print(f"Schema '{self.config.schema}' already exists.")
            
            print(f"Database connection established. Search path configured for schema '{self.config.schema}'.")
            return True
        except Exception as e:
            print(f"Error during database connection or schema setup for schema '{self.config.schema}': {str(e)}")
            self.engine = None # Reset engine on failure
            return False
            
    def _is_safe_select_query(self, sql: str) -> bool:
        """Return True if the SQL is a single SELECT statement (no DML/DDL)."""
        # Remove leading/trailing whitespace and comments
        stripped = sql.strip().lower()
        # Remove SQL comments (simple -- and /* */)
        import re
        stripped = re.sub(r"(--.*?$)|(/\*.*?\*/)", "", stripped, flags=re.MULTILINE|re.DOTALL).strip()
        # Only allow queries that start with 'select'
        return stripped.startswith("select")

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame."""
        if not self._is_safe_select_query(sql):
            print("Blocked non-SELECT or unsafe SQL query.")
            return pd.DataFrame()
        try:
            if self.engine is None:
                self.connect()
            result = pd.read_sql(sql, self.engine)
            return result
        except Exception as e:
            print(f"Error executing query: {str(e)}")
            return pd.DataFrame()
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        """Get schema information for a table."""
        query = f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = '{self.config.schema}'
        AND table_name = '{table_name}'
        ORDER BY ordinal_position;
        """
        return self.execute_query(query).to_dict('records')

# Security Incidents Schema Definition
SECURITY_INCIDENTS_SCHEMA = {
    "incident_id": {"type": "INTEGER", "description": "Unique identifier for the security incident"},
    "timestamp": {"type": "TIMESTAMP", "description": "When the incident occurred"},
    "severity": {"type": "TEXT", "description": "Severity level (Low, Medium, High, Critical)"},
    "category": {"type": "TEXT", "description": "Type of incident (e.g., Phishing, Malware, Unauthorized Access)"},
    "description": {"type": "TEXT", "description": "Detailed description of the incident"},
    "status": {"type": "TEXT", "description": "Current status (Open, In Progress, Resolved, Closed)"},
    "affected_systems": {"type": "TEXT", "description": "Comma-separated list of affected systems"},
    "reported_by": {"type": "TEXT", "description": "Name/ID of person who reported the incident"},
    "assigned_to": {"type": "TEXT", "description": "Name/ID of person handling the incident"},
    "resolution_notes": {"type": "TEXT", "description": "Notes on resolution (if resolved)"}
}

# Function Declarations for Gemini
def create_function_declarations() -> types.Tool:
    """Create function declarations for Gemini model."""
    
    # Function to query security incidents
    query_incidents_func = types.FunctionDeclaration(
        name="query_security_incidents",
        description="Query the security incidents database with SQL",
        parameters={
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string",
                    "description": "SQL query to execute against the security_incidents table"
                }
            },
            "required": ["sql_query"]
        }
    )
    
    # Function to get schema information
    get_schema_func = types.FunctionDeclaration(
        name="get_security_incidents_schema",
        description="Get schema information for the security incidents table",
        parameters={
            "type": "object",
            "properties": {}
        }
    )
    
    # Create tool with both function declarations
    security_tool = types.Tool(
        function_declarations=[
            query_incidents_func,
            get_schema_func
        ]
    )
    
    return security_tool

# AI Agent for Security Incidents
class SecurityIncidentsAgent:
    """AI agent for querying security incidents database with natural language."""
    
    SYSTEM_INSTRUCTION = """
You are an AI assistant that helps security analysts query a database of security incidents.

ALWAYS follow this workflow:
1. When asked about security incidents, FIRST call the get_security_incidents_schema function to retrieve the current schema of the security_incidents table.
2. Use only the fields and their exact names as returned in the schema when generating any SQL queries.
3. Convert the user's natural language query into a safe, parameterized SQL query using the query_security_incidents function.
4. After getting the data, provide a concise summary of the findings.
5. Format the data in a readable way when presenting.

When writing SQL:
- Use proper column names and table name (security_incidents) as shown in the schema.
- Use parameterized queries when possible to prevent SQL injection.
- Add appropriate WHERE clauses to filter data.
- Add ORDER BY for sorting if needed.
- Use appropriate JOINs if needed to connect with other tables.
- Use **PostgreSQL SQL syntax for all queries**. For date calculations, use expressions like NOW() - INTERVAL '30 days'. Do NOT use SQLite syntax such as date('now', '-30 days').

Respond in a professional and helpful manner suitable for security analysts.
"""

    def __init__(
        self,
        db_connector: DatabaseConnector,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.2
    ):
        self.db_connector = db_connector
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.tools = create_function_declarations()
        self.client = genai.Client(api_key=self.api_key)
        self.chat = None

    def initialize_chat(self):
        """Initialize the Gemini chat session."""
        print(f"Initializing Gemini chat: {self.model_name}")
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            tools=[self.tools],
            system_instruction=self.SYSTEM_INSTRUCTION
        )
        self.chat = self.client.chats.create(
            model=self.model_name,
            config=config
        )

    def handle_function_call(self, function_call: types.FunctionCall, debug_log=None):
        if debug_log is None:
            debug_log = []
        function_name = function_call.name
        function_args = dict(function_call.args)
        if function_name == "query_security_incidents":
            sql_query = function_args.get("sql_query")
            # Post-process SQL to convert common SQLite date patterns to PostgreSQL
            if sql_query:
                sql_query = sql_query.replace("date('now', '-30 days')", "NOW() - INTERVAL '30 days'")
                sql_query = sql_query.replace('date(\'now\', \'-7 days\')', "NOW() - INTERVAL '7 days'")
                sql_query = sql_query.replace('date(\'now\', \'-1 day\')', "NOW() - INTERVAL '1 day'")
                sql_query = sql_query.replace('date(\'now\')', 'NOW()')
            debug_log.append(f"Executing SQL query: {sql_query}")
            results = self.db_connector.execute_query(sql_query)
            return results.to_dict('records')
        elif function_name == "get_security_incidents_schema":
            debug_log.append("Getting security incidents schema")
            return SECURITY_INCIDENTS_SCHEMA
        else:
            debug_log.append(f"Unknown function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}

    def query(self, user_query: str) -> Dict:
        debug_log = []
        if self.chat is None:
            self.initialize_chat()
            debug_log.append(f"Initializing Gemini chat: {self.model_name}")
        try:
            debug_log.append(f"Sending query to Gemini: {user_query}")
            response = self.chat.send_message(user_query)
            # Loop: handle function calls until we get a text response
            while response.candidates and response.candidates[0].content.parts:
                function_call_found = False
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_to_call = part.function_call
                        debug_log.append(f"Handling function call: {function_to_call.name}")
                        function_result = self.handle_function_call(function_to_call, debug_log)
                        debug_log.append(f"Sending function result to Gemini for function: {function_to_call.name}")
                        response = self.chat.send_message(
                            types.Part.from_function_response(
                                name=function_to_call.name,
                                response={"content": function_result}
                            )
                        )
                        function_call_found = True
                        break  # Only handle one function call at a time
                if not function_call_found:
                    break  # No more function calls, exit loop
            final_text = response.text
            return {
                "response": final_text,
                "status": "success",
                "debug_log": debug_log
            }
        except Exception as e:
            debug_log.append(f"Error processing query: {str(e)}")
            return {
                "response": f"Error processing your query: {str(e)}",
                "status": "error",
                "debug_log": debug_log
            }

# Main application
def main():
    load_dotenv()  # Load environment variables from .env file

    # Configuration
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set it to your Google AI Studio API Key.")
        return
    
    DB_CONFIG = DatabaseConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "security"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "password"),
        schema=os.environ.get("DB_SCHEMA", "public")  # Added schema configuration
    )
    
    # Initialize database connector
    db_connector = DatabaseConnector(DB_CONFIG)
    if not db_connector.connect(): # Try to connect early
        print("Failed to connect to the database. Please check your configuration.")
        return
    
    # Initialize the security incidents agent with API key
    agent = SecurityIncidentsAgent(db_connector, api_key=GEMINI_API_KEY)
    
    # Example query
    example_query = "Show me all critical security incidents from the past week"
    print(f"\nSending example query to agent: '{example_query}'")
    result = agent.query(example_query)
    
    print("\nQuery:", example_query)
    print("Response:", result.get("response", "No response text found."))
    print("Status:", result.get("status", "unknown"))

if __name__ == "__main__":
    main()
