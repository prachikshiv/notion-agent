import streamlit as st
import google.generativeai as genai
from notion_client import Client

# 1. ENFORCE PRIVACY (Password Protect the App)
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    st.set_page_config(page_title="OSAI Private Copilot", page_icon="💀", layout="centered")
    st.title("💀 Private OSAI Study Agent")
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

# 2. RUNTIME SECRETS INITIALIZATION
NOTION_TOKEN = st.secrets["NOTION_TOKEN_VALUE"]
PAGE_ID = st.secrets["PAGE_ID_VALUE"]
GEMINI_KEY = st.secrets["GEMINI_KEY_VALUE"]

# Initialize official API Clients
notion = Client(auth=NOTION_TOKEN)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-3.8-flash") 

# 3. DEEP RECURSIVE DATA HARVESTER (HANDLES MULTIPLE SUBPAGES)
def get_notion_notes(page_id):
    text_content = []
    
    def crawl_page(target_id, depth=0):
        # Safety gate to prevent infinite loops or timeout crashes
        if depth > 5: 
            return
        try:
            response = notion.blocks.children.list(block_id=target_id)
            blocks = response.get("results", [])
            
            for block in blocks:
                block_type = block.get("type")
                
                # EDGE CASE FIXED: If the block is an embedded subpage, extract its ID and crawl it
                if block_type == "child_page":
                    subpage_title = block.get("child_page", {}).get("title", "Untitled Subpage")
                    text_content.append(f"\n--- Entering Subpage: {subpage_title} --- \n")
                    crawl_page(block.get("id"), depth + 1)
                    continue

                # Parse standard technical layout blocks
                supported_types = ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "toggle", "callout", "code", "quote"]
                if block_type in supported_types:
                    rich_text = block.get(block_type, {}).get("rich_text", [])
                    block_text = "".join([t.get("plain_text", "") for t in rich_text])
                    
                    if block_text:
                        if block_type == "code": 
                            text_content.append(f"\n[CODE BLOCK]\n{block_text}\n[END CODE]\n")
                        else: 
                            text_content.append(block_text)
                            
                # Parse standard block nested indentation structures
                if block.get("has_children") and block_type != "child_page":
                    try:
                        child_res = notion.blocks.children.list(block_id=block.get("id"))
                        for child in child_res.get("results", []):
                            c_type = child.get("type")
                            if c_type in ["paragraph", "bulleted_list_item", "code"]:
                                c_text = "".join([t.get("plain_text", "") for t in child.get(c_type, {}).get("rich_text", [])])
                                if c_text: text_content.append(c_text)
                    except Exception:
                        continue
        except Exception as e:
            # Append execution error hints inline without breaking the main engine run
            text_content.append(f"[Error crawling sub-element {target_id}: {str(e)}]")

    crawl_page(page_id)
    master_notes = "\n".join(text_content).strip()
    return "CRITICAL_ERROR_EMPTY" if not master_notes else master_notes

# 4. COPILOT SESSION ENGINE
st.title("💀 OSAI OffSec Exam Proctor & Copilot")
st.caption("Deep-linked to your parent layout and all nested subpages.")

if "messages" not in st.session_state: 
    st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): 
        st.markdown(msg["content"])

if user_prompt := st.chat_input("Enter a concept, URL, or status update..."):
    with st.chat_message("user"): 
        st.markdown(user_prompt)
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    
    live_notes = get_notion_notes(PAGE_ID)
    if "CRITICAL_ERROR_EMPTY" in live_notes or not live_notes.strip():
        st.error("⛔ ERROR: The agent cannot pull data from your Notion page layout! Verify your token is shared down to all child subpages.")
        st.stop()

    system_instructions = (
        f"You are a local OSAI OffSec Exam Copilot. Rely strictly on these notes compiled from all subpages:\n\n{live_notes}\n\n"
        "STRICT EXECUTION PROTOCOL:\n"
        "1. GROUNDING: Look up the current target or milestone provided by the student within your notes. "
        "If the query is NOT addressed in the notes, explicitly reply: 'I cannot find an offensive playbook for this scenario in your notes.' Do not invent external methodologies.\n"
        "2. CONTEXTUAL REASONING: Print the immediate next sequential command or tool invocation from the notes.\n"
        "3. SCANNABILITY: Provide a direct assessment, followed by next actions in code blocks."
    )
    
    conversation_history = [{"role": "user", "parts": [system_instructions]}]
    for m in st.session_state.messages:
        role_label = "model" if m["role"] == "assistant" else "user"
        conversation_history.append({"role": role_label, "parts": [m["content"]]})
        
    with st.chat_message("assistant"):
        try:
            response = model.generate_content(conversation_history)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e: 
            st.error(f"Failed to reach Gemini API backend: {str(e)}")
