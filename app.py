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
model = genai.GenerativeModel("gemini-3.8-flash") 

# 3. UPGRADED RECURSIVE LIVE NOTION DATA HARVESTER
def get_notion_notes(page_id):
    url = f"https://notion.com{page_id}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
    }
    
    def fetch_blocks(block_id):
        text_content = []
        try:
            res = requests.get(f"https://notion.com{block_id}/children", headers=headers)
            if res.status_code != 200:
                return []
            
            blocks = res.json().get("results", [])
            for block in blocks:
                block_type = block.get("type")
                
                # Extract text based on block layout (including lists, code blocks, callouts, and toggles)
                if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "toggle", "callout", "code"]:
                    rich_text = block.get(block_type, {}).get("rich_text", [])
                    block_text = "".join([t.get("plain_text", "") for t in rich_text])
                    if block_text:
                        # Explicitly tag code blocks for the AI to recognize payload syntax
                        if block_type == "code":
                            text_content.append(f"\n[CODE BLOCK]\n{block_text}\n[END CODE]\n")
                        else:
                            text_content.append(block_text)
                
                # Recursively extract text hidden inside nested layouts (like indented bullet paths or toggles)
                if block.get("has_children"):
                    text_content.extend(fetch_blocks(block.get("id")))
                    
            return text_content
        except Exception:
            return []

    all_notes = fetch_blocks(page_id)
    if not all_notes:
        return "CRITICAL_ERROR_EMPTY"
    return "\n".join(all_notes)

# 4. STREAMLIT INTERFACE & EXAM CHAT INTERACTION
st.title("💀 OSAI OffSec Exam Proctor & Copilot")
st.caption("Live-linked to your evolving Notion study workspace.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display current chat stream
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input Entry
if user_prompt := st.chat_input("Enter a concept, URL, or status update..."):
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # Harvest fresh text blocks recursively on every prompt execution
    with st.spinner("Harvesting updated playbooks from Notion..."):
        live_notes = get_notion_notes(PAGE_ID)

    # HARD GROUNDING GATE: Freeze execution if the live data pull fails or is blank
    if not live_notes or live_notes.strip() == "CRITICAL_ERROR_EMPTY":
        st.error("⛔ ERROR: The agent cannot pull data from your Notion page! Verify your integration token is added to the page connection settings.")
        st.stop()

    # State-Aware Custom Prompt Engine
    system_instructions = (
        f"You are a local OSAI OffSec Exam Copilot. Your sole purpose is to keep the student on track "
        f"using the exact steps, playbooks, and methodologies defined in these notes:\n\n{live_notes}\n\n"
        "STRICT EXECUTION PROTOCOL:\n"
        "1. GROUNDING: Look up the current target, URL, or milestone provided by the student within your notes. "
        "If the user asks a question or presents a tactical scenario that is NOT addressed in the notes, "
        "explicitly reply: 'I cannot find an offensive playbook for this scenario in your notes.' Do not invent external methodologies or generic tool definitions.\n"
        "2. CONTEXTUAL REASONING: Print the immediate next sequential command, flag parameters, or tool invocation from the notes.\n"
        "3. SCANNABILITY: Provide a direct assessment, followed by next actions in code blocks."
    )

    # Format history payload for Gemini API
    conversation_history = [{"role": "user", "parts": [system_instructions]}]
    for m in st.session_state.messages:
        role_label = "model" if m["role"] == "assistant" else "user"
        conversation_history.append({"role": role_label, "parts": [m["content"]]})

    # Generate streaming response
    with st.chat_message("assistant"):
        try:
            response = model.generate_content(conversation_history)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            error_msg = f"Failed to reach Gemini API backend: {str(e)}"
            st.error(error_msg)
