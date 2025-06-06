import streamlit as st
import json
import time
import google.generativeai as genai

# --- Google Generative AI Configuration ---
# IMPORTANT: In the Canvas environment, leave API_KEY as an empty string.
# The Canvas runtime will automatically provide the API key for your fetch calls.
API_KEY = "" # Your API Key for local testing outside Canvas. Do NOT paste a real key here for Canvas.

try:
    if API_KEY: # Only configure if an API key is provided (for local testing)
        genai.configure(api_key=API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Failed to initialize Gemini model: {str(e)}")
    st.info("Please ensure you have an API key configured if running locally, or that the Canvas environment provides it.")
    st.stop()


# --- Mock Data and Responses for Simulation ---
MOCK_FILE_CONTENT = {
    "report.pdf": "## Report Summary\n\nThis is a mock PDF content converted to Markdown. It discusses key findings for the year 2024, focusing on market trends and growth opportunities.",
    "data.xlsx": "| Header 1 | Header 2 |\n|---|---|\n| Data 1 | Data 2 |\n| Data 3 | Data 4 |\n\nThis is a mock spreadsheet content converted to Markdown, showing tabular data.",
    "script.py": "```python\ndef hello_openhands_versa():\n    print('Hello from OpenHands-Versa Python script!')\nhello_openhands_versa()\n```\n\nThis is a mock Python script content.",
    "index.html": "```html\n<!DOCTYPE html>\n<html>\n<head><title>Mock Webpage</title><script src='[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)'></script></head>\n<body class='p-4 bg-gray-100 font-inter'>\n    <h1 class='text-2xl font-bold mb-4'>Welcome to Mock Website!</h1>\n    <p class='mb-2'>This is some sample text on the page.</p>\n    <button id='btn1' class='bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md shadow-md'>Click Me</button>\n    <a id='link1' href='[https://mock-website.com/about](https://mock-website.com/about)' class='text-blue-600 hover:underline ml-4'>About Us</a>\n</body>\n</html>\n```\n\nThis is a mock HTML file content."
}

# --- Agent Tools (Simulated) ---

def execute_bash_command(command):
    """Simulates bash shell execution."""
    st.session_state.logs.append(f"Executing Bash: {command}")
    if command.startswith('ls'):
        return f"stdout: {' '.join(MOCK_FILE_CONTENT.keys())}\nstderr: "
    elif command.startswith('echo'):
        return f"stdout: {command[len('echo '):]}\nstderr: "
    else:
        return f"stdout: Command \"{command}\" executed successfully (simulated).\nstderr: "

def execute_python_code(code):
    """Simulates Python code execution via IPython."""
    st.session_state.logs.append(f"Executing Python:\n{code}")
    if "print('Hello from OpenHands-Versa Python script!')" in code:
        return f"stdout: Hello from OpenHands-Versa Python script!\nstderr: "
    else:
        return f"stdout: Python code executed (simulated). Output depends on code logic.\nstderr: "

def browse_web(url, action_type, element_id=None, text_input=None):
    """Simulates multimodal web browsing with context condensation."""
    st.session_state.logs.append(f"Browsing: {action_type} {url} (Element: {element_id or 'N/A'}, Text: {text_input or 'N/A'})")

    screenshot_url = "https://placehold.co/400x300/e0e0e0/000000?text=Mock+Screenshot"
    ax_tree = f"""
        <MockAXTree>
            <Page title="Mock Webpage" url="{url}">
                <Element type="h1" text="Welcome to Mock Website!"/>
                <Element type="p" text="This is some sample text on the page."/>
                <Element type="button" id="btn1" text="Click Me"/>
                <Element type="link" id="link1" href="https://mock-website.com/about" text="About Us"/>
            </Page>
        </MockAXTree>
    """
    interactable_elements = [
        {"id": 'btn1', "type": 'button', "text": 'Click Me', "bounding_box": 'x:100, y:200, w:80, h:40'},
        {"id": 'link1', "type": 'link', "text": 'About Us', "bounding_box": 'x:200, y:200, w:100, h:30'},
    ]

    observation = {
        "action": action_type,
        "url": url,
        "screenshot": screenshot_url,
        "axTree": ax_tree,
        "interactableElements": interactable_elements,
        "message": f"Successfully performed {action_type} on {url}."
    }
    return observation

def search_web(query):
    """Simulates web search using an API (like Tavily)."""
    st.session_state.logs.append(f"Searching Web: {query}")
    results = [
        {"title": f"Result 1 for {query}", "snippet": f"This is a snippet from search result 1 related to \"{query}\".", "url": f"https://search.example.com/result1?q={query}"},
        {"title": f"Result 2 for {query}", "snippet": f"A second snippet, providing more information about \"{query}\".", "url": f"https://search.example.com/result2?q={query}"},
    ]
    return results

def process_file(filename):
    """Simulates multimodal file processing (e.g., PDF to Markdown)."""
    st.session_state.logs.append(f"Processing file: {filename}")
    content = MOCK_FILE_CONTENT.get(filename)
    if content:
        return f"File: {filename}\nContent (Markdown conversion simulated):\n{content}"
    else:
        return f"Error: File \"{filename}\" not found (simulated)."

def edit_file(filename, content):
    """Simulates a file editing operation. In a real scenario, this would interact with the file system."""
    st.session_state.logs.append(f"Editing file: {filename}")
    if filename in MOCK_FILE_CONTENT:
        MOCK_FILE_CONTENT[filename] = content # Update mock for demonstration
        return f"Successfully edited file: {filename}. Content updated (simulated)."
    else:
        return f"Error: File \"{filename}\" not found for editing (simulated)."

# --- LLM Decision Making (Using Gemini) ---
def _build_history_for_gemini(chat_history):
    """Converts Streamlit chat history format to Gemini-compatible format."""
    gemini_formatted_history = []
    for entry in chat_history:
        role = "user" if entry['role'] == 'user' else "model"
        # For model responses, extract only the tool output part that the LLM needs to see
        # The LLM needs to know what was *output* by the tool, not the agent's internal action description
        text_content = entry['parts'][0]['text']
        if role == "model" and "Tool Output:" in text_content:
            tool_output_raw_str = text_content.split('Tool Output:', 1)[1].strip()
            # Attempt to parse it if it was a JSON string originally
            try:
                tool_output_data = json.loads(tool_output_raw_str)
                text_content = f"Tool Output (Parsed): {json.dumps(tool_output_data, indent=2)}"
            except json.JSONDecodeError:
                text_content = f"Tool Output: {tool_output_raw_str}"
        
        gemini_formatted_history.append({"role": role, "parts": [{"text": text_content}]})
    return gemini_formatted_history

def simulate_llm_decision_gemini(chat_history):
    """
    Uses Gemini 1.5 Flash to decide the next agent tool and arguments.
    """
    st.session_state.logs.append("Querying Gemini model for next action...")

    # Define the structured output schema for the LLM
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "tool": {"type": "STRING", "description": "The name of the tool to use (e.g., execute_bash_command, browse_web, search_web, process_file, edit_file, execute_python_code, finish, plan)."},
            "args": {
                "type": "OBJECT",
                "description": "A dictionary of arguments for the selected tool.",
                "properties": {
                    "command": {"type": "STRING", "description": "Command for execute_bash_command"},
                    "code": {"type": "STRING", "description": "Python code for execute_python_code"},
                    "url": {"type": "STRING", "description": "URL for browse_web"},
                    "action_type": {"type": "STRING", "description": "Action type for browse_web (e.g., 'navigate', 'click', 'type')"},
                    "element_id": {"type": "STRING", "description": "Element ID for browse_web actions"},
                    "text_input": {"type": "STRING", "description": "Text input for browse_web 'type' action"},
                    "query": {"type": "STRING", "description": "Search query for search_web"},
                    "filename": {"type": "STRING", "description": "Filename for process_file or edit_file"},
                    "content": {"type": "STRING", "description": "New content for edit_file"},
                    "message": {"type": "STRING", "description": "Completion message for 'finish' tool"},
                    "plan": {"type": "STRING", "description": "Plan description for 'plan' tool"}
                },
            }
        },
        "required": ["tool", "args"]
    }

    # System instruction to guide the LLM
    system_instruction = (
        "You are OpenHands-Versa, a generalist AI agent designed to solve diverse tasks using "
        "a minimal set of general tools: code editing and execution, web search, "
        "multimodal web browsing, and file access. "
        "Your goal is to complete the user's task by selecting the most appropriate tool and its arguments. "
        "Always respond with a JSON object containing 'tool' and 'args' keys. "
        "The 'tool' key must be one of the following: "
        "'execute_bash_command', 'execute_python_code', 'browse_web', 'search_web', 'process_file', 'edit_file', 'finish', 'plan'. "
        "The 'args' key must be a dictionary of arguments relevant to the chosen tool. "
        "If you believe the task is complete or no further actions are necessary, use the 'finish' tool with a 'message' argument. "
        "If you need to outline a multi-step approach, use the 'plan' tool with a 'plan' argument. "
        "Here are the available tools and their arguments:\n"
        "- `execute_bash_command(command: str)`\n"
        "- `execute_python_code(code: str)`\n"
        "- `browse_web(url: str, action_type: str, element_id: str = None, text_input: str = None)`\n"
        "- `search_web(query: str)`\n"
        "- `process_file(filename: str)`\n"
        "- `edit_file(filename: str, content: str)`\n"
        "- `finish(message: str)`\n"
        "- `plan(plan: str)`\n\n"
        "Analyze the current chat history and determine the next logical step. "
        "If the user asks to perform an action, select the tool. "
        "If the user asks for a high-level approach or asks 'what is the next step?', provide a 'plan'."
    )

    full_gemini_history = _build_history_for_gemini(chat_history)
    
    try:
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }

        contents_for_gemini = [
            {"role": "user", "parts": [{"text": system_instruction}]}
        ]
        for entry in full_gemini_history:
            contents_for_gemini.append(entry)

        gemini_response = gemini_model.generate_content(
            contents=contents_for_gemini,
            generation_config=generation_config
        )

        st.session_state.logs.append(f"Gemini raw response: {gemini_response}")

        if gemini_response and gemini_response.candidates:
            if gemini_response.candidates[0].content and gemini_response.candidates[0].content.parts:
                response_text = gemini_response.candidates[0].content.parts[0].text
                st.session_state.logs.append(f"Gemini parsed text: {response_text}")
                decision = json.loads(response_text)
                return decision
            else:
                st.session_state.logs.append("Gemini response content or parts are empty.")
                return {'tool': 'finish', 'args': {'message': "Gemini did not return a valid response content."}}
        else:
            st.session_state.logs.append("Gemini did not return any candidates.")
            return {'tool': 'finish', 'args': {'message': "Gemini did not return any candidates."}}

    except Exception as e:
        st.session_state.logs.append(f"Error calling Gemini API: {e}")
        st.error(f"Error during LLM decision: {e}. Please check your API key and network connection.")
        return {'tool': 'finish', 'args': {'message': f"LLM error: {e}"}}

# --- Streamlit Application ---

def render_tool_output(output):
    """Renders the tool output in a user-friendly format."""
    if isinstance(output, str):
        # Attempt to parse output if it's a JSON string representing tool output
        if output.startswith('Tool Output:'):
            content = output[len('Tool Output:'):].strip()
            try:
                json_content = json.loads(content)
                if isinstance(json_content, list) and json_content and 'url' in json_content[0]:
                    st.write(f"**Search Results:**")
                    for res in json_content:
                        st.markdown(f"- [{res.get('title', res.get('url'))}]({res.get('url')})")
                        st.markdown(f"  *{res.get('snippet')}*")
                    return
                elif isinstance(json_content, dict) and 'action' in json_content and 'url' in json_content:
                    st.write(f"**Browsing Observation:**")
                    st.write(f"Action: {json_content.get('action')}")
                    st.write(f"URL: {json_content.get('url')}")
                    # Placeholder for screenshot, as Streamlit cannot directly render external base64
                    st.image(json_content.get('screenshot', "https://placehold.co/400x300/e0e0e0/000000?text=Mock+Screenshot"), caption="Mock Screenshot", use_column_width=True)
                    st.code(json_content.get('axTree'), language='xml')
                    st.write(f"Interactable Elements:")
                    for el in json_content.get('interactableElements', []):
                        st.markdown(f"- {el.get('type')} (ID: {el.get('id')}): {el.get('text')} [Box: {el.get('bounding_box')}]")
                    st.write(f"Message: {json_content.get('message')}")
                    return
            except json.JSONDecodeError:
                pass # Not JSON, proceed to check other formats

            if content.startswith('File:'):
                lines = content.split('\n')
                file_name = lines[0].replace('File:', '').strip()
                file_content_start_idx = next((i for i, line in enumerate(lines) if "Content (Markdown conversion simulated):" in line), -1)
                if file_content_start_idx != -1:
                    file_content = "\n".join(lines[file_content_start_idx+1:]).strip()
                    st.write(f"**File Content: {file_name}**")
                    st.code(file_content, language='markdown') # Using code block for markdown content
                    return
        st.code(output, language='text') # Default for plain text output
    else:
        st.write(str(output)) # Fallback for non-string outputs

def simulate_agent_step(current_prompt):
    """
    Simulates a multi-step agent interaction based on the current prompt.
    Updates the chat history in session state.
    """
    # Clear logs for a new task submission
    if st.session_state.get('last_prompt_submitted') != current_prompt:
        st.session_state.logs = []
        st.session_state.last_prompt_submitted = current_prompt

    # Append user prompt to history (if it's a new input)
    if not st.session_state.chat_history or st.session_state.chat_history[-1].get('role') != 'user' or st.session_state.chat_history[-1]['parts'][0]['text'] != current_prompt:
        st.session_state.chat_history.append({'role': 'user', 'parts': [{'text': current_prompt}]})

    max_steps = 2 # Reduced for quicker demonstration, balanced with allowing some multi-turn
    step_count = 0

    # Use a spinner to indicate processing
    with st.spinner("Agent thinking..."):
        while step_count < max_steps:
            # Pass the entire chat history for the LLM to make a decision
            decision = simulate_llm_decision_gemini(st.session_state.chat_history)
            st.session_state.logs.append(f"LLM Decision: {decision}")

            if not decision or decision['tool'] == 'finish':
                message = decision['args']['message'] if decision else "Agent finished. No more actions inferred by the LLM."
                st.session_state.chat_history.append({'role': 'model', 'parts': [{'text': f"Agent Action: Finish\nTool Output: {message}"}]})
                break # Exit loop if 'finish' tool is called

            tool_output = ''
            action_description = f"Agent Action: {decision['tool']}"

            try:
                # Dynamically call the mock tool function
                tool_func = globals().get(decision['tool'])
                if tool_func:
                    tool_output = tool_func(**decision['args'])
                else:
                    tool_output = f"Unknown tool: {decision['tool']}"
            except Exception as e:
                tool_output = f"Error executing tool {decision['tool']}: {e}"
                st.session_state.logs.append(f"Tool execution error: {e}")

            # Store tool output in a consistent format in chat history
            st.session_state.chat_history.append({'role': 'model', 'parts': [{'text': f"{action_description}\nTool Output: {json.dumps(tool_output) if isinstance(tool_output, (dict, list)) else str(tool_output)}"}]})
            
            # If the LLM's decision was to 'plan', it doesn't consume a concrete action step
            # that needs an observation to react to, so we just continue.
            if decision['tool'] == 'plan':
                step_count += 1
                time.sleep(0.5) # Simulate LLM thinking time
                continue 
            
            step_count += 1
            # After a tool execution (unless it's 'finish' or 'plan'),
            # add a prompt for the LLM to generate the next step based on the tool's output.
            if decision['tool'] != 'finish':
                st.session_state.chat_history.append({'role': 'user', 'parts': [{'text': f"Based on the last tool output, what is the next step to achieve the goal? (Current Task: \"{current_prompt}\")"}]})
                time.sleep(0.5) # Simulate LLM thinking time


# --- Streamlit UI Setup ---
st.set_page_config(
    page_title="OpenHands-Versa Simulator",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for styling
st.markdown("""
<style>
    /* Overall page background */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #282828; /* Changed to a slightly lighter dark grey */
        color: #E0E0E0; /* Ensure text color is light */
    }
    .reportview-container {
        background-color: #282828; /* Also apply to the main report container */
    }

    .main .block-container {
        max-width: 800px;
        padding-top: 2rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 2rem;
    }
    .stTextInput>div>div>input {
        border-radius: 0.5rem;
        border: 1px solid #4B4B4B;
        background-color: #2F2F2F;
        color: #E0E0E0;
    }
    .stButton>button {
        background-color: #4A90E2;
        color: white;
        font-weight: bold;
        border-radius: 0.5rem;
        padding: 0.75rem 1.5rem;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background-color: #357ABD;
        transform: scale(1.02);
    }
    .user-message {
        background-color: #1E90FF; /* DodgerBlue */
        color: white;
        border-radius: 1rem;
        border-bottom-right-radius: 0;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        align-self: flex-end;
    }
    .agent-message {
        background-color: #36454F; /* Charcoal */
        color: #F0F0F0;
        border-radius: 1rem;
        border-bottom-left-radius: 0;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        align-self: flex-start;
    }
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 60vh;
        overflow-y: auto;
        padding: 1rem;
        background-color: #1A1A1A;
        border-radius: 0.75rem;
        margin-bottom: 1rem;
        border: 1px solid #333;
    }
    .stCode {
        background-color: #282C34 !important;
        color: #ABB2BF !important;
        border-radius: 0.5rem;
        padding: 0.75rem;
        overflow-x: auto;
    }
    h1 {
        text-align: center;
        color: #E0E0E0;
        font-family: 'Inter', sans-serif;
    }
    p {
        text-align: center;
        color: #C0C0C0;
    }
</style>
""", unsafe_allow_html=True)


st.title("OpenHands-Versa Simulator")
st.markdown("""
<p class="text-center text-lg text-gray-300 mb-8 max-w-2xl mx-auto">
    This is a conceptual simulator demonstrating the core ideas of OpenHands-Versa:
    Coding, Multimodal Web Browsing, and Information Access.
    Enter a task, and observe the agent's simulated actions and tool outputs.
</p>
""", unsafe_allow_html=True)


# Initialize chat history and logs in session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'logs' not in st.session_state:
    st.session_state.logs = []


# Display chat history
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    if msg['role'] == 'user':
        st.markdown(f'<div class="user-message">{msg["parts"][0]["text"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="agent-message">**Agent**<br>', unsafe_allow_html=True)
        # Handle structured vs plain text tool output
        full_text = msg['parts'][0]['text']
        action_desc = full_text.split('\nTool Output:')[0]
        tool_output_str = full_text[len(action_desc + '\nTool Output:'):].strip()

        st.markdown(f"*{action_desc.replace('Agent Action: ', '')}*")
        try:
            # Attempt to parse as JSON for rich rendering
            tool_output_data = json.loads(tool_output_str)
            # The render_tool_output expects "Tool Output: " prefix to handle parsing
            render_tool_output(f"Tool Output: {json.dumps(tool_output_data)}")
        except json.JSONDecodeError:
            # Fallback for plain text
            render_tool_output(f"Tool Output: {tool_output_str}")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# Input area
task_input = st.text_input(
    "Enter your task:",
    placeholder="e.g., 'execute code', 'browse website', 'search for information', 'read report.pdf', 'edit file script.py', 'list files', 'make a plan'",
    key="task_input"
)

if st.button("Run Agent Step", use_container_width=True):
    if task_input:
        simulate_agent_step(task_input)
        st.rerun() # Rerun to update the chat history display

st.markdown("""
<div class="text-gray-400 text-sm mt-4 text-center">
    <p>Note: This is a simplified conceptual simulator. Actual OpenHands-Versa uses real tools and a complex LLM for decision-making.</p>
    <p>For the full implementation, please refer to the <a href="https://github.com/adityasoni9998/OpenHands-Versa" target="_blank" rel="noopener noreferrer" style="color: #61DAFB; text-decoration: underline;">official GitHub repository</a>.</p>
</div>
""", unsafe_allow_html=True)

# Optional: Display internal logs for debugging
with st.expander("Internal Logs"):
    for log in st.session_state.logs:
        st.code(log)
