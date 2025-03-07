import streamlit as st
import os
import pandas as pd
import shutil
from datetime import datetime

import openai
from openai import OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]
MODEL_NAME = "gpt-4o-mini"
# 기본 폴더 경로
BASE_DIR = "dir"

# 최초 실행 시 1번만 폴더 생성 (세션 상태 유지)
if "foldername" not in st.session_state:
    current_time = datetime.now()
    st.session_state.foldername = current_time.isoformat().replace(":", "_")

UPLOAD_FOLDER = os.path.join(BASE_DIR, st.session_state.foldername)

# 폴더 생성 (최초 1회만 실행됨)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def save_uploaded_file(directory, file):
    file_path = os.path.join(directory, file.name)
    
    if file.name.endswith(".txt"):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file.getvalue().decode("utf-8"))
    else:
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
    
    return st.success(f"파일 업로드 성공! ({file.name})")

# 📂 폴더 삭제 함수
def delete_folder(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)
        os.makedirs(directory, exist_ok=True)  # 빈 폴더 다시 생성
        return st.success("📂 업로드된 파일이 모두 삭제되었습니다.")

# 📂 업로드된 파일 목록 조회 함수
def get_uploaded_files(directory):
    if os.path.exists(directory):
        return os.listdir(directory)
    return []

def delete_files_and_vectorstores():
    client = st.session_state.client
    vector_stores = client.beta.vector_stores.list().data
    for vector_store in vector_stores:
        vector_store_id = vector_store.id
        all_files = list(client.beta.vector_stores.files.list(vector_store_id = vector_store_id))
        for file in all_files:
            client.files.delete(file.id)
        client.beta.vector_stores.delete(vector_store_id)

def upload_file_to_vectorstore(file):
    client = st.session_state.client
    assistant = st.session_state.assistant
    user1 = st.session_state.thread
    vector_store = st.session_state.vector_store
    
    file_paths = [os.path.join(UPLOAD_FOLDER, file.name)]
    file_streams = [open(path, "rb") for path in file_paths]

    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    st.session_state.assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

# 파일로 저장하는 함수
def save_chat_history():
    file_name = "chat_history.txt"
    
    # 채팅 데이터를 role과 message로 변환하여 텍스트로 저장
    chat_content = "\n".join(
        [f"[{chat['role'].upper()}]: {chat['message']}" for chat in st.session_state.chat_history]
    )
    
    # 파일 저장
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(chat_content)
    
    return file_name


def main():
    st.title("knowledge-chatbot")
    
    # 📂 파일 업로드 섹션
    st.header("1️⃣ 파일 업로드")
    
    if "file_uploaded" not in st.session_state:
        st.session_state.file_uploaded = False
    
    uploaded_file = st.file_uploader("파일을 업로드하세요 (PDF, DOCX, TXT)", label_visibility="collapsed", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        if st.session_state.file_uploaded is False:
            save_uploaded_file(UPLOAD_FOLDER, uploaded_file)
            upload_file_to_vectorstore(uploaded_file)
            st.session_state.file_uploaded = True
        else:
            st.write("파일 이름이 적힌 창을 닫아주어야 파일이 업로드됩니다.")

    if uploaded_file is None:
        st.session_state.file_uploaded = False
    
    # 📂 폴더 삭제 버튼 추가
    if st.button("📂 폴더 삭제"):
        delete_files_and_vectorstores()
        delete_folder(UPLOAD_FOLDER)
        st.session_state.client = OpenAI()
        st.session_state.thread = (st.session_state.client).beta.threads.create()

    st.markdown("---")

    if "client" not in st.session_state: 
        st.session_state.client = OpenAI()
        assistant = client.beta.assistants.create(
            instructions="친절한 어시스턴트 봇이다.",
            model=MODEL_NAME,
            tools=[{"type": "file_search"}]
        )
        st.session_state.assistant = assistant

    if "thread" not in st.session_state:
        user1 = client.beta.threads.create()
        st.session_state.thread = user1
    
    if "vector_store" not in st.session_state:
        client = st.session_state.client
        vector_store = client.beta.vector_stores.create(
            name="자료",
            expires_after={"anchor": "last_active_at", "days": 1}
        )
        st.session_state.vector_store = vector_store
    
    # 📋 업로드된 파일 목록 섹션
    st.header("2️⃣ 업로드된 파일 목록")
    
    files = get_uploaded_files(UPLOAD_FOLDER)

    if len(files) == 0:
        st.warning("현재 업로드된 파일이 없습니다.")
    else:
        st.success(f"현재 저장된 파일 수: {len(files)}개")
        file_df = pd.DataFrame({"파일명": files}, index=range(1, len(files) + 1))
        st.table(file_df)

    st.markdown("---")

    # 📝 챗봇 섹션
    st.header("3️⃣ 챗봇")

    # 업로드된 파일 목록 가져오기
    files = os.listdir(UPLOAD_FOLDER)
    
    if st.button("📂 대화 기록 삭제"):
        client = st.session_state.client
        st.session_state.chat_history = []
        st.session_state.thread = client.beta.threads.create()
        
        response = "대화 기록을 모두 삭제하였습니다."
        st.success(response)

    st.markdown("회의록을 작성하시려면 입력창에 **/회의록**, **/Meeting**, 또는 **/meeting_minutes** 태그를 입력한 후에 회의 제목을 입력하세요.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    for content in st.session_state.chat_history:
        with st.chat_message(content["role"]):
            st.markdown(content['message'])    
    
    if prompt := st.chat_input("메시지를 입력하세요."):
        with st.chat_message("user"):
            st.markdown(prompt)
            st.session_state.chat_history.append({"role": "user", "message": prompt})
    
        with st.chat_message("ai"):
            client = st.session_state.client
            assistant = st.session_state.assistant
            user1 = st.session_state.thread

            if(prompt.startswith("/meeting_minutes") or prompt.startswith("/회의록") or prompt.startswith("/Meeting")):
                meeting_topic = " ".join(prompt.split(" "))
                # 파일에서 전체 텍스트 읽기
                with open("prompt_meeting_minutes.txt", "r", encoding="utf-8") as file:
                    contents = file.read()
                prompt_meeting_minutes = f"""{contents}"""
                run = client.beta.threads.runs.create_and_poll(
                thread_id=user1.id,
                assistant_id=assistant.id,
                instructions=prompt_meeting_minutes
                )
                messages = client.beta.threads.messages.list(
                thread_id=user1.id
                )
        
                response = messages.data[0].content[0].text.value
                st.markdown(response)
                st.session_state.chat_history.append({"role": "ai", "message": response})
            else:
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=user1.id,
                    assistant_id=assistant.id,
                    instructions=prompt + "  \n 그리고 출처 표기는 삭제해주세요."
                )
                messages = client.beta.threads.messages.list(
                    thread_id=user1.id
                )
        
                response = messages.data[0].content[0].text.value
                st.markdown(response)
                st.session_state.chat_history.append({"role": "ai", "message": response})
    
    
    # 다운로드 버튼 생성
    if st.button("💾 채팅 기록 저장"):
        file_name = save_chat_history()
        with open(file_name, "r", encoding="utf-8") as file:
            st.download_button(
                label="📥 여기를 누르면 다운로드됩니다.",
                data=file,
                file_name="chat_history.txt",
                mime="text/plain"
            )

if __name__ == "__main__":
    main()
