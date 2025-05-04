import streamlit as st
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from docx import Document
import tempfile
import os

# === SETUP ===
openai.api_key = st.secrets["OPENAI_API_KEY"]
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# === STREAMLIT UI ===
st.title("📘 Book Summarizer")
st.write("Generate a detailed summary of a book and save it to Google Drive.")

book_title = st.text_input("Book Title")
book_notes = st.text_area("Notes, excerpts, or reflections about the book")
summary_style = st.selectbox("Summary Style", ["Narrative", "Bullet", "Professional", "Reflective"])
submit = st.button("Generate Summary")

if submit and book_title:
    # === CALL OPENAI ===
    st.write("📤 Calling OpenAI API...")
    prompt = f"""
Provide a comprehensive summary and overview of the book titled "{book_title}" using the following notes: {book_notes}.
Include:
- General summary of the book and it's purpose
- Thesis of the book and what makes it unique in its perspective
- Main takeaways and actionable insights from the book
- Chapter-by-chapter summary and key ideas
- Important quotes -- as many as possible (in-line and in a dedicated section)
Use this tone/style: {summary_style}.
Avoid markdown (**bold**, _italic_) — return clean plain text with clear structure.
    """

    try:
        from openai import OpenAI
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a literary critic and professional book summarizer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        summary_text = response.choices[0].message.content.strip()

        st.success("✅ Summary generated!")
        st.text(f"Length: {len(summary_text)} characters")

    except Exception as e:
        st.error("❌ OpenAI API call failed")
        st.exception(e)
        st.stop()

    # === CREATE .DOCX FILE ===
    try:
        st.write("📝 Creating Word document...")
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

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name

    except Exception as e:
        st.error("❌ Failed to generate Word document")
        st.exception(e)
        st.stop()

    # === UPLOAD TO GOOGLE DRIVE ===
    try:
        st.write("📤 Uploading to Google Drive...")

        file_metadata = {
            'name': f"Summary - {book_title}.docx",
            'parents': [st.secrets["GDRIVE_FOLDER_ID"]],
            'mimeType': 'application/vnd.google-apps.document'
        }

        media = MediaFileUpload(tmp_path, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        st.success("✅ Uploaded to Google Drive!")
        st.markdown(f"[📄 View Summary](https://drive.google.com/file/d/{file['id']}/view)")

    except Exception as e:
        st.error("❌ Google Drive upload failed")
        st.exception(e)
        st.stop()

    os.remove(tmp_path)
