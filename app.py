import streamlit as st
import google.generativeai as genai
import requests

# 1. ENFORCE PRIVACY (Password Protect the App)
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    if st.session_state.password_correct:
        return True

    st.set_page_config(page_title="OSAI Private Copilot", page_icon="💀", layout="centered")
    st.title("💀 Private OSAI Study Agent")
    st.markdown("🔒 *Unauthorized access is strictly prohibited.*")
    
    password = st.text_input("Enter Access Password:", type="password")
    if st.button("Authenticate"):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Access Denied.")
    return False

if not check_password():
    st.stop()

# 2. APP INITIALIZATION & CLOUD SECRETS CONFIGURATION
NOTION_TOKEN = st.secrets["NOTION_TOKEN_VALUE"]
PAGE_ID = st.secrets["PAGE_ID_VALUE"]
GEMINI_KEY = st.secrets["GEMINI_KEY_VALUE"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash") # Highly efficient for technical parsing

# 3. LIVE NOTION DATA HARVESTER
def get_notion_notes(page_id):
    url = f"https://notion.com{page_id}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Error: Unable to fetch live notes from Notion. Check your Token/Page ID configurations."
        
        blocks = response.json().get("results", [])
        text_content = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "code"]:
                # Special parsing for standard rich text blocks
                text_element = block.get(block_type, {}).get("rich_text", [])
                for text in text_element:
                    text_content.append(text.get("plain_text", ""))
        return "\n".join(text_content)
    except Exception as e:
        return f"Exception occurred during data pull: {str(e)}"

# 4. STREAMLIT INTERFACE & EXAM CHAT INTERACTION
st.title("💀 OSAI OffSec Exam Proctor & Copilot")
st.caption("Live-linked to your evolving Notion study workspace.")

# Initialize chat tracking
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display current chat stream
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Prompt Box
if user_prompt := st.chat_input("Enter a concept or ask for an exam simulation puzzle..."):
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # Pull fresh text directly from Notion on every message transaction
    with st.spinner("Harvesting updated attack vectors from Notion..."):
        live_notes = get_notion_notes(PAGE_ID)

    # Core OSAI Red Team Prompt Engine
    system_instructions = (
        f"You are a brutal OffSec OSAI Exam Proctor and Offensive AI Expert. "
        f"Ground all feedback strictly within the uploaded notes:\n\n{live_notes}\n\n"
        "CRITICAL ASSESSMENT CONTROLS:\n"
        "1. FOCUS: Challenge me exclusively on AI attack surfaces: Prompt Injection, RAG Data Poisoning, "
        "Agentic Tool Abuse, Model Extraction, Supply Chain Vulns, and pivoting into Domain Controllers.\n"
        "2. NO HAND-HOLDING: Give technical explanations in maximum 2 paragraphs. Bold framework-specific commands, "
        "exploit concepts, and tooling paths.\n"
        "3. ACTIVE SIMULATION: Always end your response with exactly ONE practical, hands-on scenario question. "
        "Structure it like an exam puzzle: give me a target scenario (e.g., an LLM orchestrator connected to a private database) "
        "and ask me to detail my next steps for enumeration, token exploitation, or boundary bypassing.\n"
        "4. ENFORCE LOOT MANAGEMENT: Remind me to look for flags and structure my evidence properly for the exam report."
    )

    # Format payload for Google Gemini API
    conversation_history = [{"role": "user", "parts": [system_instructions]}]
    for m in st.session_state.messages:
        role_label = "model" if m["role"] == "assistant" else "user"
        conversation_history.append({"role": role_label, "parts": [m["content"]]})

    # Generate response via the cloud LLM brain
    with st.chat_message("assistant"):
        try:
            response = model.generate_content(conversation_history)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            error_msg = f"Failed to reach Gemini API backend: {str(e)}"
            st.error(error_msg)
