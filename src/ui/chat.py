import uuid
import streamlit as st
from ui.stream_handler import StreamHandler

DEFAULT_TITLE = "🤖 ReAct Agent Chat"
DEFAULT_SUBTITLE = (
    "Ask me anything! I can use reasoning and tool calls to solve your problems."
)

def chat(
    agent,
    show_token_usage=True,
    page_title=DEFAULT_TITLE,
    page_subtitle=DEFAULT_SUBTITLE,
):
    st.set_page_config(
        page_title="ReAct Agent Chat",
        page_icon="🤖",
        layout="centered"
    )
    
    # Minimal, professional CSS
    st.markdown("""
        <style>
        .stChatMessage {
            padding: 1rem;
            font-size: 15px;
        }
        
        code {
            background-color: #f3f4f6;
            padding: 3px 7px;
            border-radius: 4px;
            font-size: 0.9em;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        
        pre {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        
        html {
            scroll-behavior: smooth;
        }
        
        h1, h2, h3, h4, h5, h6 {
            font-weight: 600;
        }
        
        details summary {
            cursor: pointer;
        }
        
        details summary::-webkit-details-marker {
            display: none;
        }
        
        details summary::before {
            content: '▶ ';
            display: inline-block;
            transition: transform 0.2s;
        }
        
        details[open] summary::before {
            transform: rotate(90deg);
        }
        </style>
    """, unsafe_allow_html=True)

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
            
            handler = StreamHandler(
                agent.llm.model_name, show_token_usage
            )
            
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # start with initial thinking message
            full_response = handler.get_thinking_message(iteration=1)
            message_placeholder.markdown(full_response, unsafe_allow_html=True)
            
            try:
                for chunk in st.session_state.agent.stream(
                    prompt, config=config, stream_mode="updates"
                ):
                    chunk_text = handler.process_chunk(chunk)
                    if chunk_text:
                        full_response += chunk_text
                        message_placeholder.markdown(
                            full_response, unsafe_allow_html=True
                        )
                
                # store the final response
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
                
            except Exception as e:
                error_msg = (
                    f"<div style='padding: 16px 0;'>"
                    f"<div style='font-size: 13px; color: #dc2626; margin-bottom: 8px;'>Error</div>"
                    f"<div style='font-size: 13px; color: #dc2626;'>{str(e)}</div>"
                    f"</div>"
                )
                message_placeholder.markdown(error_msg, unsafe_allow_html=True)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

    # sidebar with info
    with st.sidebar:
        st.markdown("### Session Info")
        st.markdown(f"**Thread ID:** `{st.session_state.thread_id[:8]}...`")
        st.markdown(f"**Messages:** {len(st.session_state.messages)}")
        
        if st.button("New Conversation", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("---")
        
        tools = st.session_state.agent.tools
        
        st.markdown("### Available Tools")
        for tool in tools:
            st.markdown(f"- `{tool.name}`")
        
        st.markdown("---")
        
        st.markdown("### About")
        st.markdown("""
            This ReAct agent uses reasoning and tool execution to solve complex problems.
        """)