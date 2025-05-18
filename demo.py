"""
Example usage of the Security Incidents AI Query Agent.

This script shows how to set up and use the agent to query a PostgreSQL database
containing security incidents data using natural language.
"""

import os
from dotenv import load_dotenv
from app import (
    SecurityIncidentsAgent, 
    DatabaseConnector, 
    DatabaseConfig
)

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

DB_CONFIG = DatabaseConfig(
    host=os.environ.get("DB_HOST"),
    port=int(os.environ.get("DB_PORT", "5432")),
    database=os.environ.get("DB_NAME"),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASSWORD"),
    schema=os.environ.get("DB_SCHEMA", "public")
)

# Add rich import if available
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None

def main():
    # Initialize Gemini
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set it to your Google AI Studio API Key.")
        return
    
    # Initialize database connector
    db_connector = DatabaseConnector(DB_CONFIG)
    if not db_connector.connect():
        print("Failed to connect to database. Exiting.")
        return
    
    # Create the agent
    agent = SecurityIncidentsAgent(
        db_connector=db_connector,
        api_key=GEMINI_API_KEY,
        model_name="gemini-2.0-flash",  # Using Gemini 2.0 Flash model
        temperature=0.2  # Lower temperature for more deterministic results
    )
    
    # Sample queries to demonstrate capabilities
    sample_queries = [
        "What are all critical severity incidents in the last 30 days?",
        "Show me phishing attacks targeting the finance department",
        "List all unresolved security incidents assigned to John Smith",
        "How many malware incidents were reported by the IT department last quarter?",
        "Show me the trend of security incidents by category over the last 6 months"
    ]
    
    # Interactive mode
    if USE_RICH:
        console.rule("[bold blue]Security Incidents AI Query Agent")
        console.print("[bold]Type your questions about security incidents, or choose from sample queries:")
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("#", style="dim", width=3)
        table.add_column("Sample Query")
        for i, query in enumerate(sample_queries, 1):
            table.add_row(str(i), query)
        console.print(table)
        console.print("[bold yellow]Type 'exit' to quit")
        console.rule("[bold blue]")
    else:
        print("Security Incidents AI Query Agent")
        print("=================================")
        print("Type your questions about security incidents, or choose from sample queries:")
        print("Sample queries:")
        for i, query in enumerate(sample_queries, 1):
            print(f"{i}. {query}")
        print("Type 'exit' to quit")
        print("=================================")
    
    while True:
        # Get user input
        if USE_RICH:
            user_input = Prompt.ask("[bold blue]\nEnter your query or sample number (1-5)")
        else:
            user_input = input("\nEnter your query or sample number (1-5): ")
        
        # Check if user wants to exit
        if user_input.lower() == 'exit':
            if USE_RICH:
                console.print("[bold red]Exiting...")
            else:
                print("Exiting...")
            break
        
        # Check if user selected a sample query
        if user_input.isdigit() and 1 <= int(user_input) <= len(sample_queries):
            query = sample_queries[int(user_input) - 1]
            if USE_RICH:
                console.print(Panel(f"Selected query: [bold]{query}", title="Sample Query", style="blue"))
            else:
                print(f"Selected query: {query}")
        else:
            query = user_input
        
        # Process the query
        if USE_RICH:
            console.print(Panel("Processing query...", style="yellow"))
        else:
            print("\nProcessing query...")
        result = agent.query(query)
        
        # Display the result
        if USE_RICH:
            console.rule("[bold blue]Response")
            if result["status"] == "success":
                console.print(Panel(result["response"], style="green", title="AI Response"))
            else:
                console.print(Panel(result["response"], style="red", title="Error"))
            console.rule("[bold blue]")
        else:
            print("\nResponse:")
            print("=================================")
            print(result["response"])
            print("=================================")

if __name__ == "__main__":
    main()
