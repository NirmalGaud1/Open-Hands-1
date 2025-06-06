import streamlit as st
import google.generativeai as genai
import subprocess
import re
import os
import json
from typing import List, Dict, Any
import logging
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure Gemini API
API_KEY = "AIzaSyA-9-lTQTWdNM43YdOXMQwGKDy0SrMwo6c"
genai.configure(api_key=API_KEY)
try:
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Failed to initialize Gemini model: {str(e)}")
    st.stop()

# Create uploads directory
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

class OpenHandsVersaAgent:
    def __init__(self, max_steps: int = 100, planning_interval: int = 10, context_window: int = 1):
        self.max_steps = max_steps
        self.planning_interval = planning_interval
        self.context_window = context_window
        self.event_stream = []  # Stores action-observation pairs
        self.step_count = 0
        self.tools = {
            "bash": self.execute_bash,
            "code_execute": self.execute_python,
            "browse": self.browse_html,
            "search": self.search_knowledge_base,
            "file_view": self.view_file,
            "plan": self.plan_task
        }
        # Simulated knowledge base
        self.knowledge_base = {
            "python syntax": "Python is a high-level programming language with clear syntax. Example: print('Hello, World!') outputs text to the console.",
            "html basics": "HTML uses tags like <button>, <a>, <input> to structure web content."
        }

    def execute_bash(self, command: str) -> str:
        """Execute a bash command and return the output."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            output = result.stdout if result.stdout else result.stderr
            logging.info(f"Bash command executed: {command}\nOutput: {output}")
            return output
        except Exception as e:
            logging.error(f"Bash execution failed: {str(e)}")
            return f"Error: {str(e)}"

    def execute_python(self, code: str) -> str:
        """Execute Python code and return the output."""
        try:
            # Clean code by removing Markdown or extra characters
            code = re.sub(r'```python\n|```', '', code).strip()
            with open("temp_code.py", "w") as f:
                f.write(code)
            result = subprocess.run(["python", "temp_code.py"], capture_output=True, text=True)
            output = result.stdout if result.stdout else result.stderr
            logging.info(f"Python code executed:\n{code}\nOutput: {output}")
            os.remove("temp_code.py")
            return output
        except Exception as e:
            logging.error(f"Python execution failed: {str(e)}")
            return f"Error: {str(e)}"

    def browse_html(self, html_path: str) -> str:
        """Simulate browsing by parsing an HTML file and extracting interactable elements."""
        try:
            if not os.path.exists(html_path):
                logging.error(f"HTML file not found: {html_path}")
                return f"Error: File {html_path} not found"
            
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            elements = []
            for tag in ["button", "a", "input"]:
                pattern = rf'<{tag}[^>]*>(.*?)</{tag}>'
                matches = re.findall(pattern, content, re.DOTALL)
                for i, match in enumerate(matches):
                    elements.append(f"{tag}_{i}: {match.strip()}")
            
            observation = "Webpage elements:\n" + "\n".join(elements) if elements else "No interactable elements found."
            logging.info(f"Browsed {html_path}:\n{observation}")
            return observation
        except Exception as e:
            logging.error(f"Browsing failed: {str(e)}")
            return f"Error: {str(e)}"

    def search_knowledge_base(self, query: str) -> str:
        """Simulate web search by querying a local knowledge base."""
        try:
            result = self.knowledge_base.get(query.lower(), "No information found.")
            logging.info(f"Search query: {query}\nResult: {result}")
            return result
        except Exception as e:
            logging.error(f"Search failed: {str(e)}")
            return f"Error: {str(e)}"

    def view_file(self, file_path: str) -> str:
        """View content of a text-based file."""
        try:
            if not os.path.exists(file_path):
                logging.error(f"File not found: {file_path}")
                return f"Error: File {file_path} not found"
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            logging.info(f"File viewed: {file_path}\nContent: {content}")
            return content
        except Exception as e:
            logging.error(f"File viewing failed: {str(e)}")
            return f"Error: {str(e)}"

    def plan_task(self, task: str) -> str:
        """Generate a plan using Gemini API."""
        try:
            recent_events = self.event_stream[-self.context_window:] if self.event_stream else []
            summary = f"Progress after {self.step_count} steps:\n"
            for event in recent_events:
                summary += f"Action: {event['action']}, Observation: {event['observation']}\n"
            
            prompt = f"Task: {task}\n{summary}\nGenerate a concise plan for the next steps, specifying which tools (bash, code_execute, browse, search, file_view) to use. Avoid code blocks or extra formatting."
            response = gemini_model.generate_content(prompt)
            plan = response.text.strip()
            logging.info(f"Plan generated:\n{plan}")
            return plan
        except Exception as e:
            logging.error(f"Planning failed: {str(e)}")
            return f"Error: {str(e)}"

    def select_tool(self, task: str) -> str:
        """Select the appropriate tool using Gemini API."""
        try:
            prompt = f"Task: {task}\nAvailable tools: bash, code_execute, browse, search, file_view, plan\nSelect the most appropriate tool for the task. Return only the tool name, no explanation or formatting."
            response = gemini_model.generate_content(prompt)
            tool = response.text.strip()
            if tool not in self.tools:
                tool = "plan"
            logging.info(f"Selected tool: {tool}")
            return tool
        except Exception as e:
            logging.error(f"Tool selection failed: {str(e)}")
            return "plan"

    def generate_tool_input(self, tool: str, task: str, uploaded_files: List[str]) -> str:
        """Generate input for the selected tool using Gemini API, considering uploaded files."""
        try:
            if tool in ["browse", "file_view"]:
                if not uploaded_files:
                    return "Error: No files uploaded for browsing or viewing."
                files_str = ", ".join(uploaded_files)
                prompt = f"Task: {task}\nTool: {tool}\nAvailable uploaded files: {files_str}\nSelect the appropriate file name for the task. Return only the file name, no path or extra text."
            elif tool == "code_execute":
                prompt = f"Task: {task}\nTool: {tool}\nGenerate clean Python code to accomplish the task. Return only the code, no Markdown, no triple backticks, no extra text."
            else:
                prompt = f"Task: {task}\nTool: {tool}\nGenerate the appropriate input for the tool (e.g., bash command, search query). Return only the input, no explanation or formatting."
            response = gemini_model.generate_content(prompt)
            tool_input = response.text.strip()
            logging.info(f"Generated input for {tool}: {tool_input}")
            if tool in ["browse", "file_view"] and tool_input:
                tool_input = os.path.join(UPLOAD_DIR, tool_input)
            return tool_input
        except Exception as e:
            logging.error(f"Tool input generation failed: {str(e)}")
            return ""

    def run(self, task: str, uploaded_files: List[str]) -> str:
        """Main agent loop to process tasks."""
        logging.info(f"Starting task: {task}")
        result = ""
        self.step_count = 0
        self.event_stream = []

        while self.step_count < self.max_steps:
            tool = self.select_tool(task)
            st.session_state["current_tool"] = tool
            st.session_state["step_count"] = self.step_count + 1

            if tool == "plan":
                observation = self.plan_task(task)
            else:
                tool_input = self.generate_tool_input(tool, task, uploaded_files)
                if "error" in tool_input.lower():
                    observation = tool_input
                else:
                    observation = self.tools[tool](tool_input)

            self.event_stream.append({"action": f"{tool}: {tool_input}", "observation": observation})
            if len(self.event_stream) > self.context_window:
                self.event_stream = self.event_stream[-self.context_window:]
            self.step_count += 1
            result = observation

            st.session_state["event_stream"] = self.event_stream
            st.session_state["last_result"] = result

            if "error" not in result.lower():
                return result  # Stop after one step for Streamlit interactivity
            else:
                return result

        return result

# Streamlit UI
st.title("OpenHands-Versa Agent")
st.markdown("An AI agent inspired by *Coding Agents with Multimodal Browsing are Generalist Problem Solvers*")

# Initialize session state
if "event_stream" not in st.session_state:
    st.session_state["event_stream"] = []
if "last_result" not in st.session_state:
    st.session_state["last_result"] = ""
if "current_tool" not in st.session_state:
    st.session_state["current_tool"] = ""
if "step_count" not in st.session_state:
    st.session_state["step_count"] = 0
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = []

# File upload section
st.subheader("Upload Files")
st.markdown("Upload HTML, text, or Markdown files to be processed by the agent (e.g., for browsing or viewing).")
uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True, type=["html", "txt", "md"])

# Process uploaded files
if uploaded_files:
    st.session_state["uploaded_files"] = []
    for uploaded_file in uploaded_files:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state["uploaded_files"].append(uploaded_file.name)
    st.success(f"Uploaded files: {', '.join(st.session_state['uploaded_files'])}")

# Display uploaded files
if st.session_state["uploaded_files"]:
    st.markdown("**Uploaded Files:**")
    for file_name in st.session_state["uploaded_files"]:
        st.markdown(f"- {file_name}")

# Task input
st.subheader("Enter Your Task")
task = st.text_area("Describe your task:", placeholder="e.g., Write a Python script, browse an uploaded HTML file, read an uploaded Markdown file...", key="task_input")
execute_button = st.button("Execute Task")

# Initialize agent
agent = OpenHandsVersaAgent(max_steps=10, planning_interval=3, context_window=1)

# Execute task
if execute_button and task:
    with st.spinner("Processing task..."):
        try:
            result = agent.run(task, st.session_state["uploaded_files"])
            if "error" in result.lower():
                st.error(f"Task failed: {result}")
            else:
                st.success("Task executed successfully!")
                st.markdown("**Result:**")
                st.code(result, language="text")
        except Exception as e:
            st.error(f"Task failed: {str(e)}")  # Fixed line

# Display current tool and step
st.markdown(f"**Current Tool:** {st.session_state['current_tool']}")
st.markdown(f"**Step Count:** {st.session_state['step_count']}")

# Display event stream
st.subheader("Event Stream")
if st.session_state["event_stream"]:
    for event in st.session_state["event_stream"]:
        st.markdown(f"**Action:** {event['action']}")
        st.markdown("**Observation:**")
        st.code(event['observation'], language="text")
        st.markdown("---")
else:
    st.markdown("No events yet.")

# Example tasks
st.subheader("Try Example Tasks")
example_tasks = [
    "Write a Python script to print 'Hello, World!'",
    "Browse an uploaded HTML file to list interactable elements",
    "Search for information about Python syntax",
    "Read an uploaded Markdown file",
    "Run a bash command to list directory contents of uploads folder"
]
for ex_task in example_tasks:
    if st.button(ex_task, key=f"example_{ex_task}"):
        with st.spinner("Processing example task..."):
            try:
                result = agent.run(ex_task, st.session_state["uploaded_files"])
                if "error" in result.lower():
                    st.error(f"Task failed: {result}")
                else:
                    st.success("Task executed successfully!")
                    st.markdown("**Result:**")
                    st.code(result, language="text")
            except Exception as e:
                st.error(f"Task failed: {str(e)}")

# Clean up uploads
def cleanup_uploads():
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR)

if st.button("Clear Uploaded Files"):
    cleanup_uploads()
    st.session_state["uploaded_files"] = []
    st.success("Uploaded files cleared.")
