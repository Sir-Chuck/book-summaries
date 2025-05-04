import streamlit as st
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from docx import Document
import tempfile
import os

# === SETUP ===
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Google Drive API setup (with service account)
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# === STREAMLIT UI ===
st.title("📘 Book Summarizer")
st.write("Generate detailed summaries and upload to Google Drive")

book_title = st.text_input("Book Title")
book_notes = st.text_area("Notes or Description")
summary_style = st.selectbox("Summary Style", ["Narrative", "Bullet", "Professional", "Reflective"])
submit = st.button("Generate Summary")

if submit and book_title and book_notes:
    with st.spinner("Generating summary..."):
        # === PROMPT ===
        prompt = f"""
        Provide a comprehensive summary and overview of the book titled "{book_title}" using the following notes: {book_notes}.
        Include:
        - General summary
        - Thesis of the book
        - Main takeaways
        - Chapter-by-chapter key ideas
        - Important quotes (in-line and in a dedicated section)
        Please use the summary style: {summary_style}. Do NOT use markdown (**bold**, _italic_) formatting.
        """

        # === CALL OPENAI ===
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a literary critic and professional book summarizer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        summary_text = response.choices[0].message.content.strip()

        # === CREATE DOCX ===
        doc = Document()
        doc.add_heading(f"📘 {book_title}", level=1)
        for section in summary_text.split("\n\n"):
            lines = section.strip().split("\n")
            if len(lines) == 1:
                doc.add_paragraph(lines[0])
            else:
                doc.add_heading(lines[0], level=2)
                for line in lines[1:]:
                    if line.strip().startswith(("-", "•", "1.")):
                        doc.add_paragraph(line.strip()[2:], style='List Bullet')
                    else:
                        doc.add_paragraph(line.strip())

        # === SAVE TEMP DOC AND UPLOAD ===
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name

        file_metadata = {
            'name': f'Summary - {book_title}.docx',
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [st.secrets["GDRIVE_FOLDER_ID"]]
        }
        media = {'name': os.path.basename(tmp_path), 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        media_body = build('drive', 'v3', credentials=credentials).files().create(
            body=file_metadata,
            media_body=tmp_path,
            fields='id'
        ).execute()

        st.success("✅ Summary generated and uploaded to Google Drive!")
        st.markdown(f"📂 [Open in Drive](https://drive.google.com/file/d/{media_body['id']}/view)")

        os.remove(tmp_path)
