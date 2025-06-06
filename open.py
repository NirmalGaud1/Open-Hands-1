import streamlit as st
import google.generativeai as genai
import subprocess
import re
import os
import json
from typing import List, Dict, Any
import logging

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
        # Simulated knowledge base (replace with real search API in practice)
        self.knowledge_base = {
            "python syntax": "Python is a high-level programming language with clear syntax...",
            "html basics": "HTML uses tags like <button>, <a>, <input> to structure web content..."
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
            
            prompt = f"Task: {task}\n{summary}\nGenerate a plan for the next steps, including which tools to use (bash, code_execute, browse, search, file_view)."
            response = gemini_model.generate_content(prompt)
            plan = response.text
            logging.info(f"Plan generated:\n{plan}")
            return plan
        except Exception as e:
            logging.error(f"Planning failed: {str(e)}")
            return f"Error: {str(e)}"

    def select_tool(self, task: str) -> str:
        """Select the appropriate tool using Gemini API."""
        try:
            prompt = f"Task: {task}\nAvailable tools: bash, code_execute, browse, search, file_view, plan\n" \
                     f"Select the most appropriate tool for the task. Return only the tool name."
            response = gemini_model.generate_content(prompt)
            tool = response.text.strip()
            if tool not in self.tools:
                tool = "plan"  # Default to planning if invalid tool
            logging.info(f"Selected tool: {tool}")
            return tool
        except Exception as e:
            logging.error(f"Tool selection failed: {str(e)}")
            return "plan"

    def generate_tool_input(self, tool: str, task: str) -> str:
        """Generate input for the selected tool using Gemini API."""
        try:
            prompt = f"Task: {task}\nTool: {tool}\nGenerate the appropriate input for the tool (e.g., bash command, Python code, file path, search query)."
            response = gemini_model.generate_content(prompt)
            tool_input = response.text.strip()
            logging.info(f"Generated input for {tool}: {tool_input}")
            return tool_input
        except Exception as e:
            logging.error(f"Tool input generation failed: {str(e)}")
            return ""

    def run(self, task: str) -> str:
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
                tool_input = self.generate_tool_input(tool, task)
                if not tool_input:
                    observation = f"Error: Failed to generate input for {tool}"
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
st.write("An AI agent inspired by 'Coding Agents with Multimodal Browsing are Generalist Problem Solvers'")

# Initialize session state
if "event_stream" not in st.session_state:
    st.session_state["event_stream"] = []
if "last_result" not in st.session_state:
    st.session_state["last_result"] = ""
if "current_tool" not in st.session_state:
    st.session_state["current_tool"] = ""
if "step_count" not in st.session_state:
    st.session_state["step_count"] = 0

# Task input
task = st.text_area("Enter your task:", placeholder="e.g., Write a Python script, browse an HTML file, search for information...")
execute_button = st.button("Execute Task")

# Initialize agent
agent = OpenHandsVersaAgent(max_steps=10, planning_interval=3, context_window=1)

if execute_button and task:
    with st.spinner("Processing task..."):
        result = agent.run(task)
        st.success("Task executed!")
        st.write("**Result:**")
        st.write(result)

# Display current tool and step
st.write(f"**Current Tool:** {st.session_state['current_tool']}")
st.write(f"**Step Count:** {st.session_state['step_count']}")

# Display event stream
st.subheader("Event Stream")
if st.session_state["event_stream"]:
    for event in st.session_state["event_stream"]:
        st.write(f"**Action:** {event['action']}")
        st.write(f"**Observation:** {event['observation']}")
        st.write("---")
else:
    st.write("No events yet.")

# Example tasks
st.subheader("Try Example Tasks")
example_tasks = [
    "Write a Python script to print 'Hello, World!'",
    "Browse the HTML file 'test.html' to list interactable elements",
    "Search for information about Python syntax",
    "Read the Markdown file 'notes.md'",
    "Run a bash command to list directory contents"
]
for ex_task in example_tasks:
    if st.button(ex_task):
        task = ex_task
        with st.spinner("Processing example task..."):
            result = agent.run(task)
            st.success("Task executed!")
            st.write("**Result:**")
            st.write(result)
