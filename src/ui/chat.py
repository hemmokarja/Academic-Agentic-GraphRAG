import uuid
import streamlit as st
from ui.stream_handler import StreamHandler

DEFAULT_TITLE = "🤖 ReAct Agent Chat"
DEFAULT_SUBTITLE = (
    "Ask me anything! I can use reasoning and tool calls to solve your problems."
)


def _apply_global_styling():
    with open("src/ui/styles.css", "r") as f:
        styles = f.read()

    st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)


def _render_sidebar():
    with st.sidebar:
        
        st.markdown(f"**Thread ID:** `{st.session_state.thread_id[:8]}...`")

        if st.button("🔄 New Conversation", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")

        tools = st.session_state.agent.tools
        tool_names_list = "\n".join([f"- `{t.name}`" for t in tools])
        
        st.header("🛠️ Tools")
        st.markdown(tool_names_list)

        st.markdown("---")
        
        st.header("ℹ️ About")
        st.markdown("This ReAct agent uses reasoning and tool execution to solve complex problems.")


def chat(
    agent,
    page_title=DEFAULT_TITLE,
    page_subtitle=DEFAULT_SUBTITLE,
):
    st.set_page_config(
        page_title="ReAct Agent Chat",
        page_icon="🤖",
        layout="centered"
    )

    _apply_global_styling()

    st.title(page_title)
    st.markdown(page_subtitle)

    if "agent" not in st.session_state:
        st.session_state.agent = agent

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

    if prompt := st.chat_input("What would you like to know?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # display assistant response with streaming
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            handler = StreamHandler(agent.model_name)

            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # start with initial thinking message
            full_response = handler.get_thinking_message(iteration=1)
            message_placeholder.markdown(full_response, unsafe_allow_html=True)

            for chunk in st.session_state.agent.stream(
                prompt, config=config, stream_mode="updates"
            ):
                chunk_text = handler.process_chunk(chunk)
                if chunk_text:
                    full_response += chunk_text
                    message_placeholder.markdown(full_response, unsafe_allow_html=True)

            # store the final response
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

    _render_sidebar()
