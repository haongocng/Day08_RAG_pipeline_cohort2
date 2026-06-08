"""
Streamlit RAG Chatbot v2 for the group project.

Run:
    streamlit run group_project/app.py
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src import task10_generation as generation  # noqa: E402

generation = importlib.reload(generation)
SUGGESTED_QUESTIONS = generation.SUGGESTED_QUESTIONS


st.set_page_config(
    page_title="DrugLaw RAG Chatbot",
    page_icon="⚖️",
    layout="wide",
)


FOLLOW_UP_MARKERS = {
    "vậy", "họ", "người này", "người đó", "bị cáo buộc", "bị truy tố",
    "còn", "thêm", "như vậy", "vụ này", "trường hợp này", "hành vi đó",
}

ANCHOR_TERMS = {
    "chi dân", "an tây", "andrea", "trúc phương", "hữu tín", "vn10",
    "điều 249", "điều 250", "điều 251", "bộ luật", "luật phòng",
    "nghị định", "cai nghiện",
}


def _is_follow_up(current_query: str) -> bool:
    lowered = current_query.lower()
    has_follow_marker = any(marker in lowered for marker in FOLLOW_UP_MARKERS)
    has_anchor = any(anchor in lowered for anchor in ANCHOR_TERMS)
    return has_follow_marker and not has_anchor


def build_contextual_query(messages: list[dict], current_query: str) -> str:
    """
    Keep retrieval clean for complete questions, and only rewrite true follow-ups.

    Earlier versions passed the whole transcript into retrieval. That made new
    questions inherit unrelated low-confidence answers and pushed good news
    chunks below legal chunks. Here, a complete question stays unchanged; a
    pronoun-heavy follow-up is resolved with the latest user topic only.
    """
    if not _is_follow_up(current_query):
        return current_query

    previous_user_questions = [
        message["content"].strip().replace("\n", " ")
        for message in messages
        if message["role"] == "user"
    ]
    if not previous_user_questions:
        return current_query

    previous_topic = previous_user_questions[-1]
    return f"{previous_topic}\nCâu hỏi tiếp theo: {current_query}"


def submit_prompt(prompt_text: str) -> None:
    st.session_state.pending_prompt = prompt_text


def source_card(source: dict, index: int) -> None:
    metadata = source.get("metadata", {})
    title = generation.citation_label(source, index)
    source_file = metadata.get("source") or metadata.get("path") or f"Source {index}"
    score = float(source.get("score", 0.0))
    retriever = metadata.get("retriever", source.get("source", "unknown"))
    doc_type = metadata.get("type", metadata.get("doc_type", "unknown"))

    with st.expander(f"{index}. {title} · score {score:.3f}", expanded=False):
        st.caption(f"File: {source_file} | Type: {doc_type} | Retrieval: {retriever}")
        st.write(source.get("content", "")[:1800])


def render_sources(sources: list[dict], title: str = "Source documents") -> None:
    if sources:
        st.subheader(title)
        for index, source in enumerate(sources, 1):
            source_card(source, index)
    else:
        st.info("Không có source document được truy xuất.")


def call_generate_with_citation(query: str, top_k: int, use_reranking: bool) -> dict:
    """
    Reload generation module before each call to avoid Streamlit stale imports.

    If an old function is somehow still loaded, fall back gracefully instead of
    crashing the UI with "unexpected keyword argument".
    """
    current_generation = importlib.reload(generation)
    generate_fn = current_generation.generate_with_citation
    signature = inspect.signature(generate_fn)
    if "use_reranking" in signature.parameters:
        return generate_fn(query, top_k=top_k, use_reranking=use_reranking)

    result = generate_fn(query, top_k=top_k)
    result["use_reranking"] = None
    result["ui_warning"] = "Module generation cũ chưa hỗ trợ bật/tắt rerank; hãy restart Streamlit."
    return result


st.title("RAG Chatbot - Pháp luật ma túy và tin tức liên quan")

with st.sidebar:
    st.header("Cấu hình")
    top_k = st.slider("Số source chunks", min_value=3, max_value=8, value=5)
    use_reranking = st.toggle(
        "Bật rerank",
        value=True,
        help="Bật để dùng Jina reranker sau bước semantic + BM25; tắt để dùng kết quả hybrid/RRF trực tiếp.",
    )
    show_contextual_query = st.checkbox("Hiển thị query có memory", value=False)

    if st.button("Xóa hội thoại"):
        st.session_state.messages = []
        st.session_state.last_sources = []
        st.session_state.pending_prompt = None
        st.session_state.stop_requested = False
        st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False


st.caption("Một vài câu hỏi mẫu")
sample_cols = st.columns(len(SUGGESTED_QUESTIONS))
for col, question in zip(sample_cols, SUGGESTED_QUESTIONS):
    with col:
        if st.button(question, use_container_width=True):
            submit_prompt(question)
            st.rerun()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


typed_prompt = st.chat_input("Nhập câu hỏi về pháp luật ma túy hoặc tin tức liên quan...")
if typed_prompt:
    submit_prompt(typed_prompt)


if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    st.session_state.stop_requested = False

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    contextual_query = build_contextual_query(st.session_state.messages[:-1], prompt)

    with st.chat_message("assistant"):
        stop_col, status_col = st.columns([1, 4])
        with stop_col:
            if st.button("Dừng", key=f"stop_{len(st.session_state.messages)}"):
                st.session_state.stop_requested = True
                st.warning(
                    "Đã yêu cầu dừng. Với lời gọi API đồng bộ, Streamlit sẽ dừng ở lần rerun kế tiếp."
                )
                st.stop()

        with status_col:
            with st.status("Đang truy xuất tài liệu và tạo câu trả lời có citation...", expanded=False):
                if st.session_state.stop_requested:
                    st.stop()
                result = call_generate_with_citation(
                    contextual_query,
                    top_k,
                    use_reranking,
                )
                answer = result["answer"]
                sources = result.get("sources", [])

        mode_label = "Rerank" if result.get("use_reranking") else "No rerank"
        st.caption(f"Mode: {mode_label}")
        st.markdown(answer)

        confidence = result.get("confidence", "normal")
        if result.get("ui_warning"):
            st.warning(result["ui_warning"])
        if confidence in {"low", "no_evidence", "out_of_scope", "blocked"}:
            st.warning("Câu trả lời này có độ tin cậy thấp hoặc nằm ngoài phạm vi dữ liệu hiện có.")

        if show_contextual_query:
            with st.expander("Query dùng cho retrieval/generation"):
                st.code(contextual_query)

        render_sources(sources)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.last_sources = sources
