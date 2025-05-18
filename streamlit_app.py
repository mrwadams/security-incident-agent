import os
import streamlit as st
from dotenv import load_dotenv
from app import SecurityIncidentsAgent, DatabaseConnector, DatabaseConfig

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DB_CONFIG = DatabaseConfig(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    database=os.environ.get("DB_NAME", "security"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "password"),
    schema=os.environ.get("DB_SCHEMA", "public")
)

SAMPLE_QUERIES = [
    "What are all critical severity incidents in the last 30 days?",
    "Show me phishing attacks targeting the finance department",
    "List all unresolved security incidents assigned to John Smith",
    "How many malware incidents were reported by the IT department last quarter?",
    "Show me the trend of security incidents by category over the last 6 months"
]


def format_debug_log(log_lines):
    formatted = []
    for line in log_lines:
        if "error" in line.lower():
            formatted.append(f"*** {line} ***")
        else:
            formatted.append(line)
    return "\n\n".join(formatted) 

st.set_page_config(
    page_title="Security Incidents AI Query Agent",
    page_icon="🛡️",
    layout="centered"
)
st.title("🛡️ Security Incidents AI Query Agent")

# --- Chat history in session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # Each item: {role, content, sql, raw}

# Connection status
@st.cache_resource(show_spinner=False)
def get_agent():
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not set. Please check your environment variables."
    db_connector = DatabaseConnector(DB_CONFIG)
    if not db_connector.connect():
        return None, "Failed to connect to the database. Please check your configuration."
    agent = SecurityIncidentsAgent(db_connector, api_key=GEMINI_API_KEY)
    return agent, None

agent, conn_error = get_agent()

if conn_error:
    st.error(conn_error)
    st.stop()

# --- Chat history display ---
if not st.session_state.chat_history:
    # Show a friendly assistant welcome message with example queries
    with st.chat_message("ai"):
        st.markdown("""
Hi! 👋 I'm your Security Incidents AI Query Agent. You can ask me questions about your security incidents database in natural language.

Here are some example queries you can try:
""")
        for q in SAMPLE_QUERIES:
            st.markdown(f"- {q}")

for entry in st.session_state.chat_history:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])
        if entry["role"] == "ai":
            if entry.get("debug_log"):
                with st.expander("Show technical details"):
                    st.text_area("Debug Log", value=format_debug_log(entry["debug_log"]), height=200)

# --- Chat input at the bottom ---
placeholder = "Ask a question about security incidents..."
user_query = st.chat_input(placeholder)

if user_query:
    # Add user message to chat history
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_query
    })
    with st.chat_message("user"):
        st.markdown(user_query)
    # Agent step-by-step (for expander only)
    steps = [
        "Parsing your question...",
        "Generating SQL query...",
        "Querying the database...",
        "Formatting the response..."
    ]
    with st.spinner("Contacting the agent..."):
        result = agent.query(user_query)
    sql = result.get("sql") if isinstance(result, dict) else None
    raw = result.get("raw") if isinstance(result, dict) else None
    # Final answer with expander for details
    with st.chat_message("ai"):
        if result["status"] == "success":
            st.markdown("**AI Response:**")
            st.write(result["response"])
            if result.get("debug_log"):
                with st.expander("Show technical details"):
                    st.text_area("Debug Log", value=format_debug_log(result["debug_log"]), height=200)
        else:
            st.error(result["response"])
    # Add agent response to chat history
    st.session_state.chat_history.append({
        "role": "ai",
        "content": result["response"] if result["status"] == "success" else result["response"],
        "debug_log": result.get("debug_log", [])
    })