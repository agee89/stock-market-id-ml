import streamlit as st
import time
import os

st.set_page_config(page_title="System Logs", page_icon="📝", layout="wide")

st.title("📝 System Logs (Backend)")
st.caption("View logs from the AI Trainer and API. Useful for debugging Mass Retrain progress.")

# Configuration: Auto-detect Log File
POSSIBLE_PATHS = [
    "logs/app.log",
    "../logs/app.log",
    "../../logs/app.log",
    "/app/logs/app.log",
    os.path.abspath("logs/app.log"),
    "/Users/gafurmog/Documents/MyProject/stock-market-id-ml/logs/app.log"
]

LOG_FILE = None
for p in POSSIBLE_PATHS:
    if os.path.exists(p):
        LOG_FILE = p
        break

if not LOG_FILE:
    st.error(f"⚠️ Log file not found.")
    
    # Debug Info
    cwd = os.getcwd()
    st.warning(f"Debugging Info:\n- Current Working Directory: `{cwd}`\n- Files in CWD: `{os.listdir(cwd)}`")
    
    # Try searching recursively in parent dirs (up to 3 levels)
    st.info("Attempting deep search...")
    found_deep = False
    for root, dirs, files in os.walk(os.path.abspath(os.path.join(cwd, "../.."))):
        if "app.log" in files:
            full_path = os.path.join(root, "app.log")
            st.success(f"Found at: {full_path}")
            LOG_FILE = full_path
            found_deep = True
            break
        # Limit depth to avoid scanning whole disk
        if root.count(os.sep) - cwd.count(os.sep) > 2:
            del dirs[:] 
            
    if not found_deep:
        st.error("Deep search failed. Please ensure 'logs/app.log' exists and is readable.")
        LOG_FILE = "logs/app.log" # Fallback



# Sidebar
with st.sidebar:
    st.header("Log Settings")
    lines_to_show = st.slider("Lines to Show", 50, 2000, 200, step=50)
    auto_refresh = st.checkbox("Auto Refresh (5s)", value=False)
    
    st.divider()
    filter_level = st.multiselect("Filter Level", ["INFO", "WARNING", "ERROR", "CRITICAL"], default=["INFO", "WARNING", "ERROR"])
    search_term = st.text_input("Search Keyword", placeholder="e.g. ASII.JK or Trainer")
    
    if st.button("🗑️ Clear Logs (Archive)"):
        # We probably can't delete if owned by root in docker, but we can try to truncate
        try:
            with open(LOG_FILE, 'w') as f:
                f.write(f"--- Log Cleared by User at {time.ctime()} ---\n")
            st.success("Log cleared!")
            st.rerun()
        except Exception as e:
            st.error(f"Cannot clear log: {e}")

# Function to read logs
def read_logs(file_path, n=200):
    if not os.path.exists(file_path):
        return ["Log file not found."]
    
    # Efficiently read last n lines
    # For small n, just readlines() is fine. For 3MB file, readlines is okay.
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Seek to end? No, simplified:
            lines = f.readlines()
            return lines[-n:]
    except Exception as e:
        return [f"Error reading log: {e}"]

def parse_log_line(line):
    # Loguru format: "2025-12-16 19:00:00.123 | LEVEL | module:func:line - Message"
    # Simple semantic coloring
    if "ERROR" in line:
        return f":red[{line.strip()}]"
    elif "WARNING" in line:
        return f":orange[{line.strip()}]"
    elif "SUCCESS" in line:
        return f":green[{line.strip()}]"
    else:
        return line.strip()

# Main View
col_head_1, col_head_2 = st.columns([0.8, 0.2])
with col_head_1:
    st.caption(f"Reading log from: `{LOG_FILE}` ({os.path.getsize(LOG_FILE)/1024:.1f} KB)")
with col_head_2:
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

st.divider()

if auto_refresh:
    time.sleep(5)
    st.rerun()

try:
    raw_lines = read_logs(LOG_FILE, 2000) # Read max 2000, then filter python side
    
    # Filter
    filtered_lines = []
    for line in raw_lines:
        # Check Level
        passed_level = False
        for lvl in filter_level:
            if f"| {lvl}" in line or (lvl=="INFO" and "| INFO" in line):
                passed_level = True
                break
        
        if not passed_level: continue
        
        # Check Search
        if search_term and search_term.lower() not in line.lower():
            continue
            
        filtered_lines.append(line)
    
    # Slice to User limit
    display_lines = filtered_lines[-lines_to_show:]
    
    # Display
    # Display with Colors + Scroll
    with st.container(height=500):
        st.code("".join(display_lines), language="log")
    
    # Alternative: Colored markdown (slower for large text)
    # for line in display_lines:
    #     st.markdown(parse_log_line(line))

except Exception as e:
    st.error(f"Viewer Error: {e}")
