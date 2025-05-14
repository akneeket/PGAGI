import streamlit as st
from PyPDF2 import PdfReader
import google.generativeai as genai
import re
import time

# --- API Setup ---
genai.configure(api_key="place your key here")  # Replace with your API key
MODEL_NAME = "models/gemini-1.5-flash"

# --- Helper Functions ---
def read_resume(file):
    pdf = PdfReader(file)
    text = ""
    for page in pdf.pages:
        content = page.extract_text()
        if content:
            text += content
    return text


def generate_technical_questions_gemini(tech_stack, resume_text, language, difficulty, retries=3):
    model = genai.GenerativeModel(MODEL_NAME)

    prompt = (
        f"You are a highly experienced technical interviewer.\n"
        f"Your task is to generate exactly 5 technical interview questions in {language}, suitable for a candidate with {difficulty.lower()}-level skills.\n"
        f"Requirements:\n"
        f"- 3 questions must be about coding, data structures, algorithms, or software concepts relevant to this tech stack: {tech_stack}\n"
        f"- 2 questions must be based on the candidate's resume:\n\n{resume_text}\n\n"
        f"- Ask questions that are clear, concise, and end with a question mark.\n"
        f"- Return only a numbered list of 5 questions, like:\n"
        f"1. ...?\n2. ...?\n3. ...?\n4. ...?\n5. ...?"
    )

    for _ in range(retries):
        response = model.generate_content(prompt)
        raw_text = response.text or ""
        questions = re.findall(r"\d+\.\s+(.*?\?)", raw_text)
        if len(questions) >= 5:
            return questions[:5]
        time.sleep(1)

    # Fallback in case Gemini doesn’t follow instructions
    lines = [line.strip(" -.0123456789").strip() for line in raw_text.split('\n') if "?" in line]
    return lines[:5] if lines else ["Could not generate questions. Please try again."]


def generate_feedback_gemini(answer, question, language):
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = (
        f"You are a technical interviewer.\n\n"
        f"Analyze the candidate's response and give feedback in {language}. "
        f"Feedback must include strengths, weaknesses, and improvement suggestions in 2-3 sentences. "
        f"Also give a rating between 1 (poor) and 5 (excellent) based on the answer quality.\n\n"
        f"Question: {question}\nAnswer: {answer}\n\n"
        f"Return the response in the following format:\n"
        f"Feedback: <your feedback>\nRating: <number from 1 to 5>"
    )
    response = model.generate_content(prompt)
    output = response.text.strip() if response.text else ""

    feedback_match = re.search(r"Feedback:\s*(.+)", output)
    rating_match = re.search(r"Rating:\s*(\d)", output)

    feedback = feedback_match.group(1).strip() if feedback_match else "No feedback available."
    rating = int(rating_match.group(1)) if rating_match else 3  # fallback rating

    return feedback, rating


# --- Candidate Info Form ---
def gather_candidate_info():
    with st.form("candidate_form"):
        st.subheader("👤 Candidate Details")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number")
        exp = st.number_input("Years of Experience", 0, 50, step=1)
        position = st.text_input("Job Role You’re Applying For")
        location = st.text_input("Current Location")
        difficulty = st.selectbox("Preferred Difficulty Level", ["Easy", "Medium", "Hard"])
        language = st.selectbox("Preferred Language", ["English", "Hindi", "Spanish", "French"])
        tech_stack = st.text_input("Tech Stack (comma-separated)")
        resume = st.file_uploader("Upload Resume (PDF)", type="pdf")
        submitted = st.form_submit_button("Submit")
        if submitted and resume is not None:
            st.session_state.candidate = {
                "name": name,
                "email": email,
                "phone": phone,
                "experience": exp,
                "position": position,
                "location": location,
                "difficulty": difficulty,
                "language": language,
                "tech_stack": tech_stack,
                "resume_text": read_resume(resume)
            }
            st.session_state.questions = []
            st.session_state.answers = []
            st.session_state.submitted = False
            st.rerun()


# --- Main App ---
def main():
    st.set_page_config("Gemini Interview Assistant", layout="centered")
    st.title("🤖 Gemini Interview Assistant")

    if "candidate" not in st.session_state:
        st.session_state.candidate = None
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "answers" not in st.session_state:
        st.session_state.answers = []
    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    if not st.session_state.candidate:
        st.markdown(
            "Welcome to your personalized AI-powered interview experience. Please fill in your details to begin.")
        gather_candidate_info()
        return

    candidate = st.session_state.candidate

    st.markdown(f"### 👋 Welcome back, <strong>{candidate['name']}</strong>! Let's begin your mock interview.",
                unsafe_allow_html=True)

    st.markdown("---")

    if not st.session_state.questions:
        with st.spinner("Generating interview questions..."):
            st.session_state.questions = generate_technical_questions_gemini(
                candidate["tech_stack"],
                candidate["resume_text"],
                candidate["language"],
                candidate["difficulty"]
            )

    if not st.session_state.submitted:
        st.subheader("🧠 Answer the Following Questions")
        with st.form("answers_form"):
            answers = []
            for i, q in enumerate(st.session_state.questions):
                st.markdown(f"**Q{i + 1}:** {q}")
                a = st.text_area(f"Your Answer to Q{i + 1}", key=f"ans_{i}")
                answers.append((q, a))
            submitted = st.form_submit_button("Submit All Answers")
            if submitted:
                st.session_state.answers = answers
                st.session_state.submitted = True
                st.rerun()

    if st.session_state.submitted:
        st.markdown("## 📋 Feedback Summary")
        for i, (q, a) in enumerate(st.session_state.answers):
            st.markdown(f"### Question {i + 1}")
            st.markdown(f"**Q:** {q}")
            st.markdown(f"**Your Answer:** {a}")
            feedback, rating = generate_feedback_gemini(a, q, candidate["language"])
            st.success(f"💬 Gemini Feedback: {feedback}")
            st.slider("⭐ Gemini's Rating (1-5)", 1, 5, value=rating, key=f"rating_{i}", disabled=True)
            st.markdown("---")

        st.balloons()
        st.success("🎉 Great job! You've completed your mock interview.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔁 Ask for More Questions"):
                st.session_state.questions = []
                st.session_state.answers = []
                st.session_state.submitted = False
                st.rerun()
        with col2:
            if st.button("❌ Exit Interview"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Exited. You can close the window or restart anytime.")
                st.stop()


if __name__ == "__main__":
    main()
