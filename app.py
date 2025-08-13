from flask import Flask, render_template, request, redirect, session, send_file, flash, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import os
import io
from fpdf import FPDF
from config import Config
import re
import markdown
import json
import uuid
from collections import defaultdict, Counter
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
import time

load_dotenv() # Load environment variables from .env

# Initialize the Flask application
app = Flask(__name__)
app.config.from_object(Config)

# --- DEBUGGING: Verify SECRET_KEY is loaded ---
print(f"DEBUG STARTUP: SECRET_KEY is set: {bool(app.config.get('SECRET_KEY'))}")
if app.config.get('SECRET_KEY'):
    print(f"DEBUG STARTUP: SECRET_KEY value (first 10 chars): {str(app.config.get('SECRET_KEY'))[:10]}...")
else:
    print("DEBUG STARTUP: WARNING! SECRET_KEY is NOT set. Sessions will not persist.")
# --- END DEBUGGING ---

# Gemini setup
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")
genai.configure(api_key=API_KEY)
# We will use the model to get the response.
# The user's original code used 'gemini-2.0-flash', so we will stick to that.
model = genai.GenerativeModel('gemini-2.0-flash')

# Define the path to your fonts directory (assuming 'fonts' folder is at the root)
FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')

# --- TRAIT MAPPING FOR DYNAMIC CALCULATION ---
TRAIT_MAPPING = {
    1: {'A': 'Logical Reasoning & Problem Solving', 'B': 'Creative Arts & Design'},
    2: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    3: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    4: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    5: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    6: {'A': 'Logical Reasoning & Problem Solving', 'B': 'Creative Arts & Design'},
    7: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    8: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    9: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    10: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    11: {'A': 'Analytical & Critical Thinking', 'B': 'Creative Arts & Design'},
    12: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    13: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    14: {'A': 'Communication & Persuasion', 'B': 'Supportive & Collaborative Nature'},
    15: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    16: {'A': 'Logical Reasoning & Problem Solving', 'B': 'Creative Arts & Design'},
    17: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    18: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    19: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    20: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    21: {'A': 'STEM & Technical Aptitude', 'B': 'Creative Arts & Design'},
    22: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    23: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    24: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    25: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    26: {'A': 'STEM & Technical Aptitude', 'B': 'Creative Arts & Design'},
    27: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    28: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    29: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    30: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    31: {'A': 'Analytical & Critical Thinking', 'B': 'Creative Arts & Design'},
    32: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    33: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    34: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    35: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    36: {'A': 'Logical Reasoning & Problem Solving', 'B': 'Research & Knowledge Exploration'},
    37: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    38: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    39: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    40: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    41: {'A': 'STEM & Technical Aptitude', 'B': 'Creative Arts & Design'},
    42: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    43: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    44: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    45: {'A': 'Numerical & Quantitative Skills', 'B': 'Business & Entrepreneurship'},
    46: {'A': 'Logical Reasoning & Problem Solving', 'B': 'Creative Arts & Design'},
    47: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    48: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    49: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    50: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    51: {'A': 'Hands-on & Mechanical Skills', 'B': 'Creative Arts & Design'},
    52: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    53: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    54: {'A': 'Communication & Persuasion', 'B': 'Supportive & Collaborative Nature'},
    55: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
    56: {'A': 'Organization & Planning', 'B': 'Research & Knowledge Exploration'},
    57: {'A': 'Organization & Planning', 'B': 'Adaptability & Flexibility'},
    58: {'A': 'Emotional Intelligence & Empathy', 'B': 'Analytical & Critical Thinking'},
    59: {'A': 'Leadership & Influence', 'B': 'Supportive & Collaborative Nature'},
    60: {'A': 'Numerical & Quantitative Skills', 'B': 'Creative Arts & Design'},
}

def calculate_top_traits(user_answers, top_n=5):
    """
    Calculate the top traits based on user answers to the assessment questions.
    
    Args:
        user_answers (dict): Dictionary with question numbers as keys and 'A' or 'B' as values
                            e.g., {1: 'A', 2: 'B', 3: 'A', ...}
        top_n (int): Number of top traits to return (default: 5)
    
    Returns:
        list: List of top N trait strings
    """
    trait_counts = Counter()
    
    # Count occurrences of each trait based on user answers
    for question_num, answer in user_answers.items():
        question_int = int(question_num) if isinstance(question_num, str) else question_num
        if question_int in TRAIT_MAPPING and answer in TRAIT_MAPPING[question_int]:
            trait = TRAIT_MAPPING[question_int][answer]
            trait_counts[trait] += 1
    
    # Get the top N traits
    top_traits = [trait for trait, count in trait_counts.most_common(top_n)]
    
    return top_traits

def get_trait_summary(user_answers):
    """
    Get a summary of all traits and their frequencies.
    
    Args:
        user_answers (dict): Dictionary with question numbers as keys and 'A' or 'B' as values
    
    Returns:
        dict: Dictionary with traits as keys and their counts as values
    """
    trait_counts = Counter()
    
    for question_num, answer in user_answers.items():
        question_int = int(question_num) if isinstance(question_num, str) else question_num
        if question_int in TRAIT_MAPPING and answer in TRAIT_MAPPING[question_int]:
            trait = TRAIT_MAPPING[question_int][answer]
            trait_counts[trait] += 1
    
    return dict(trait_counts)

# --- Pydantic Models for Data Validation ---
# This model reflects the MBTI output from the AI.
class MbtiResultModel(BaseModel):
    type: str
    explanation: str
    strengths: List[str]
    weaknesses: List[str]

class CareerDetail(BaseModel):
    name: str
    match_score: float = Field(..., ge=0.0, le=100.0)
    explanation: str
    competitive_exams: List[str]
    degree_courses: List[str]

class FinalSuggestionModel(BaseModel):
    mbti_result: MbtiResultModel  
    career_alignments: List[CareerDetail] # Note: The prompt now requests exactly 8 careers.
    clarity_and_impact: str

# Dummy Firestore-like setup for Flask backend
_firestore_db = defaultdict(dict)
SESSIONS_COLLECTION_NAME = 'sessions'

def get_session_doc_ref(session_id: str):
    """Generates a dummy document reference for a session."""
    return f"{SESSIONS_COLLECTION_NAME}/{session_id}"

def get_session_data(session_id: str):
    """Retrieves a session's data from the dummy database."""
    return _firestore_db.get(get_session_doc_ref(session_id), {})

def save_session_data(session_id: str, data: dict):
    """Saves a session's data to the dummy database."""
    _firestore_db[get_session_doc_ref(session_id)] = data

# --- Assessment Questions (as a single string to be split) ---
ASSESSMENT_QUESTIONS_RAW = """
A) I enjoy solving complex logic puzzles. 
B) I prefer brainstorming imaginative stories or ideas.

A) I make detailed plans before starting anything. 
B) I go with the flow and adjust as I go.

A) I can sense people’s emotions without them telling me. 
B) I focus on facts and objective details in conversations.

A) I like taking the lead in group work. 
B) I like supporting others without being in charge.

A) I enjoy working with numbers and statistics. 
B) I enjoy sketching, painting, or designing.

A) I break problems into small, logical steps. 
B) I think of multiple creative possibilities at once.

A) I keep my workspace organized and tidy. 
B) I’m comfortable working in slightly chaotic environments.

A) I can tell when someone is upset even if they act fine. 
B) I rely on evidence and data before deciding.

A) I motivate and guide others toward a goal. 
B) I work best by contributing my part to a shared goal.

A) I calculate budgets or expenses with ease. 
B) I create visual concepts or artistic projects.

A) I enjoy identifying patterns in data. 
B) I enjoy experimenting with different artistic styles.

A) I like planning events down to the smallest detail. 
B) I like to keep plans loose and spontaneous.

A) I can comfort others when they’re stressed. 
B) I assess situations logically without emotional influence.

A) I enjoy persuading people toward my ideas. 
B) I enjoy collaborating quietly toward common goals.

A) I like solving math-related problems. 
B) I like designing visually appealing layouts.

A) I quickly understand cause-and-effect in problems. 
B) I enjoy thinking of alternative, unconventional solutions.

A) I prefer following a schedule daily. 
B) I prefer changing my routine as needed.

A) I easily empathize with characters in a story. 
B) I focus on the author’s message and reasoning.

A) I enjoy coordinating and delegating tasks. 
B) I enjoy helping without taking credit.

A) I work well with formulas and equations. 
B) I work well with images, colors, and patterns.

A) I am drawn to solving scientific or technical problems. 
B) I am drawn to artistic performances or exhibitions.

A) I prepare checklists for my activities. 
B) I handle tasks as they come without much prep.

A) I can often “read between the lines” in conversations. 
B) I prefer to stick to what’s explicitly said.

A) I enjoy being the spokesperson for a team. 
B) I enjoy working behind the scenes.

A) I feel energized when analyzing numerical trends. 
B) I feel energized when creating unique designs.

A) I like using logic to troubleshoot mechanical issues. 
B) I like using creativity to reimagine how things could be.

A) I prefer structured work environments. 
B) I prefer open-ended, flexible environments.

A) I respond compassionately when friends share problems. 
B) I offer practical advice and solutions.

A) I naturally influence group decisions. 
B) I naturally offer help where needed without leading.

A) I’m comfortable calculating percentages and ratios. 
B) I’m comfortable creating illustrations or visual content.

A) I think analytically when faced with challenges. 
B) I think creatively when faced with challenges.

A) I plan projects step-by-step. 
B) I like improvising in projects.

A) I can sense changes in someone’s mood. 
B) I focus on measurable signs or proof.

A) I like public speaking to inspire others. 
B) I like contributing through personal, quiet effort.

A) I enjoy financial problem solving. 
B) I enjoy visual arts.

A) I look for logical flaws in arguments. 
B) I think about symbolic meaning and underlying themes.

A) I like mapping out long-term goals. 
B) I like exploring options as they come.

A) I comfort friends in difficult times. 
B) I offer straightforward, logical feedback.

A) I enjoy leading brainstorming sessions. 
B) I enjoy refining and supporting existing ideas.

A) I prefer working on spreadsheets. 
B) I prefer working on visual presentations.

A) I enjoy problem-solving in coding or science. 
B) I enjoy choreographing, composing, or performing arts.

A) I keep a strict calendar for tasks. 
B) I allow room for spontaneous decisions.

A) I quickly sense group tensions. 
B) I identify process inefficiencies.

A) I influence decisions in meetings. 
B) I offer consistent team support.

A) I enjoy tracking budgets. 
B) I enjoy conceptualizing marketing campaigns.

A) I focus on practical solutions. 
B) I focus on innovative possibilities.

A) I enjoy order and organization. 
B) I enjoy change and adaptability.

A) I connect emotionally with others easily. 
B) I evaluate situations with facts.

A) I enjoy making executive decisions. 
B) I enjoy providing resources for decision-makers.

A) I feel confident using mathematics in real life. 
B) I feel confident creating visual concepts.

A) I enjoy building or repairing things. 
B) I enjoy imagining how things could be improved.

A) I prefer following clear processes. 
B) I prefer experimenting with new methods.

A) I offer emotional comfort to friends. 
B) I offer strategic solutions to friends.

A) I am persuasive in debates. 
B) I am cooperative in team efforts.

A) I enjoy interpreting graphs and charts. 
B) I enjoy creating storyboards and designs.

A) I focus on step-by-step execution. 
B) I focus on the bigger picture possibilities.

A) I like consistent daily routines. 
B) I like variety in my schedule.

A) I am sensitive to how others feel. 
B) I am more focused on factual accuracy.

A) I naturally guide group projects. 
B) I naturally assist without leading.

A) I prefer accounting and record-keeping tasks. 
B) I prefer creative marketing or design tasks.
"""

student_name = ''

def get_paged_questions(page_num, questions_per_page=12):
    questions_list = ASSESSMENT_QUESTIONS_RAW.strip().split('\n\n')
    start_index = (page_num - 1) * questions_per_page
    end_index = start_index + questions_per_page
    return questions_list[start_index:end_index], len(questions_list)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if request.method == 'POST':
        session.clear()
        session['student_name'] = request.form['student_name']
        session['graduation_subjects'] = request.form['graduation_subjects']
        session['preferred_field'] = request.form.get('preferred_field', 'None specified')
        session['country'] = 'India'
        session['tone'] = 'Professional'
        
        flash('Preferences saved. Starting assessment.', 'success')
        return redirect('/assessment/1')

    return render_template('preferences.html')

@app.route('/assessment/<int:page_num>', methods=['GET', 'POST'])
def assessment(page_num):
    questions_list, total_questions = get_paged_questions(page_num)
    # Calculate total pages, rounding up
    total_pages = (total_questions + 11) // 12

    if 'assessment_answers' not in session:
        session['assessment_answers'] = {}

    if request.method == 'POST':
        # Process form data and save answers to the session
        answers = request.form
        # Check if all questions on the current page have been answered
        expected_answers = len(questions_list)
        if len(answers) != expected_answers:
            flash("Please answer all questions before proceeding.", 'warning')
            return redirect(f"/assessment/{page_num}")
            
        for key, value in answers.items():
            if key.startswith('q'):
                global_question_index = key[1:]
                session['assessment_answers'][global_question_index] = value
        
        # Check if this is the last page
        if page_num < total_pages:
            return redirect(f'/assessment/{page_num + 1}')
        else:
            # All pages are complete, proceed to results
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            # Save the session data to our "database"
            save_session_data(session_id, dict(session)) 
            return redirect('/result')

    # For GET request, render the assessment page
    # `session.get('assessment_answers', {})` is used to pre-fill answers if the user navigates back
    return render_template('assessment_page.html', questions=questions_list, page_num=page_num, total_pages=total_pages)

@app.route('/result')
def result():
    session_id = session.get('session_id')
    if not session_id:
        flash("Assessment incomplete. Please start again.", 'warning')
        return redirect('/preferences')

    session_data = get_session_data(session_id)
    
    if not session_data.get('suggestion_data'):
        try:
            prompt = generate_prompt(session_data)
            retries = 0
            while retries < 3:
                try:
                    response = genai.GenerativeModel('gemini-2.0-flash').generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    suggestion_json_string = response.candidates[0].content.parts[0].text
                    suggestion_data_model = FinalSuggestionModel.model_validate_json(suggestion_json_string)
                    session['suggestion_data'] = suggestion_data_model.model_dump()
                    session['raw_suggestion_plain_text'] = json.dumps(session['suggestion_data'], indent=2)
                    save_session_data(session_id, dict(session))
                    break
                except (ValidationError, Exception) as e:
                    print(f"API call failed, retry {retries+1}: {e}")
                    retries += 1
                    time.sleep(2 ** retries)
            else:
                raise RuntimeError("Failed to get a valid response from the API after multiple retries.")
            
        except RuntimeError as e:
            print(f"Final API call failed: {e}")
            flash("An error occurred while generating your results. Please try again.", 'danger')
            return redirect('/preferences')
    
    suggestion_data = session.get('suggestion_data', {})
    career_alignments = suggestion_data.get('career_alignments', [])
    mbti_result = suggestion_data.get('mbti_result', {})
    
    top_traits = [
        "Creative and Adaptable",
        "Analytical and Structured",
    ]
    
    mbti_explanation = markdown.markdown(mbti_result.get('explanation', ''), extensions=['nl2br'])
    clarity_and_impact = markdown.markdown(suggestion_data.get('clarity_and_impact', ''), extensions=['nl2br'])
    
    raw_suggestion_plain_text = session.get('raw_suggestion_plain_text', '')

    global student_name 
    student_name = session_data.get('student_name', 'Student')

    return render_template(
        'result.html',
        top_traits=top_traits,
        career_alignments=career_alignments,
        clarity_and_impact=clarity_and_impact,
        mbti_result=mbti_result,
        mbti_explanation=mbti_explanation,
        raw_suggestion_plain_text=raw_suggestion_plain_text,
        student_name=student_name
    )

@app.route('/download', methods=['POST'])
def download():

    raw_suggestion_data = request.form.get('raw_suggestion_data')
    if not raw_suggestion_data:
        flash("No results to download.", 'warning')
        return redirect('/result')

    try:
        suggestion_data = json.loads(raw_suggestion_data)
        validated_data = FinalSuggestionModel.model_validate(suggestion_data)
        
        mbti_result = validated_data.mbti_result
        career_alignments_data = validated_data.career_alignments
        clarity_and_impact = validated_data.clarity_and_impact
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Error parsing or validating JSON data for download: {e}")
        flash("An error occurred while processing the download request.", 'danger')
        return redirect('/result')
    
    pdf = FPDF()
    
    try:
        pdf.add_font('DejaVuSansCondensed', '', os.path.join(FONTS_DIR, 'DejaVuSansCondensed.ttf'), uni=True)
        pdf.add_font('DejaVuSansCondensed', 'B', os.path.join(FONTS_DIR, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
        pdf.set_font('DejaVuSansCondensed', '', 12)
    except Exception as e:
        print(f"WARNING: Could not load DejaVuSansCondensed fonts: {e}. Falling back to Arial.")
        pdf.set_font("Arial", size=12)
        
    pdf.add_page()
    
    pdf.set_font('DejaVuSansCondensed', 'B', 16)
    pdf.ln()
    pdf.cell(0, 10, 'Your Personalized Career Guidance Report', ln=1, align='C')
    pdf.ln(10)


    intro1 = """We extend our heartfelt appreciation for your active participation in our psychometric assessment designed to evaluate engineering potential. Your thoughtful responses have significantly contributed to the creation of this comprehensive report, aimed at assessing your alignment with a future in engineering.

As you embark on this journey of self-discovery and academic exploration, we invite you to engage deeply with the insights presented in the following pages. This report offers a detailed analysis of your inherent strengths, preferences, and aptitudes — serving as a personalized guide to help you make informed decisions about pursuing engineering as a potential career path. We encourage you to read the report in its entirety, as each section offers a valuable perspective that contributes to a well-rounded understanding of your suitability for the field.
    """
    pdf.set_font('DejaVuSansCondensed', '', 10)
    
    # Define a width for multi_cell to prevent horizontal overflow
    page_width = pdf.w - 2 * pdf.l_margin # Calculate usable page width
    pdf.multi_cell(page_width, 5, intro1.strip()) 
    pdf.ln(10) 

    intro2=f"""
    Dear {student_name},
    """
    pdf.set_font('DejaVuSansCondensed', 'B', 11)
    pdf.multi_cell(page_width, 5, intro2.strip()) 
    pdf.ln(10)

    intro3="""Choosing a college major or academic discipline is often a complex and overwhelming decision, frequently influenced by external pressures such as job market trends, career prospects, and societal expectations. While seeking advice from parents, educators, and peers is a natural and often helpful step, it is equally important to reflect inward — to understand your own capabilities, interests, and aspirations.
    
Can we enhance our decision-making process by gaining clarity about ourselves? Are we aware of how our personal strengths and interests align with the unique demands of different academic fields?
    
Thriving in any discipline, especially engineering, requires a distinctive set of cognitive abilities — including logical reasoning, critical thinking, mathematical aptitude, and problem-solving skills. Each individual possesses a unique profile of abilities — some innate, others cultivated through experience and learning.
    
What if there were a structured and objective way to evaluate how well your natural strengths align with the demands of engineering? This report strives to do precisely that — to provide personalized, evidence-based insights to support your academic and career planning.
    """
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(page_width, 5, intro3.strip()) 
    pdf.ln(10)
    
    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.multi_cell(page_width, 10, 'Disclaimer:') 
    pdf.ln(1)
    
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(page_width, 5, 'This psychometric assessment has been developed with the intention of guiding students in evaluating their suitability for engineering studies. The analysis is based on your individual responses to scenario-based questions and should be viewed as one of several tools in your decision-making toolkit. We advise against relying solely on this report and recommend consulting with career counselors or academic advisors for additional perspective. Please refer to the terms and conditions section at the end of this report for further clarification.') 
    pdf.ln(10)
    
    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.multi_cell(page_width, 10, 'Important Note:') 
    pdf.ln(1)
    
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(page_width, 5, 'This assessment specifically focuses on alignment with engineering disciplines. A result indicating a lower alignment does not imply an absence of potential or talent in other fields. Your strengths may lie in domains not covered by this evaluation. We urge you to interpret your results within the context of engineering suitability while remaining open to exploring a broad spectrum of academic and career opportunities.') 
    pdf.ln(10)
    
    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.multi_cell(page_width, 10, 'Intended Audience:') 
    pdf.ln(1)
    
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(page_width, 5, 'This report is most beneficial for students who are in the process of selecting their undergraduate field of study, parents guiding their children through college decisions, and individuals preparing for engineering admission counseling or considering engineering as a future course of study.') 
    pdf.ln(10)
    
    # Section for MBTI result
    pdf.set_font('DejaVuSansCondensed', 'B', 14)
    pdf.ln()
    pdf.cell(0, 10, 'MBTI Personality Analysis', ln=1)
    
    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.ln()
    pdf.cell(0, 10, f"Personality Type: {mbti_result.type}", ln=1)
    
    pdf.set_font('DejaVuSansCondensed', '', 10)
    explanation_plain = re.sub(r'[\*_`]', '', mbti_result.explanation)
    pdf.multi_cell(0, 5, f"Explanation: {explanation_plain}")
    
    pdf.set_font('DejaVuSansCondensed', 'B', 10)
    pdf.ln()
    pdf.cell(0, 10, "Strengths:", ln=1)
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(0, 5, ", ".join(mbti_result.strengths))
    
    pdf.set_font('DejaVuSansCondensed', 'B', 10)
    pdf.ln()
    pdf.cell(0, 10, "Weaknesses:", ln=1)
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.multi_cell(0, 5, ", ".join(mbti_result.weaknesses))

    pdf.ln(10) # Add a bigger space before the next section

    # The rest of the career alignments, clarity, and disclaimer sections
    pdf.set_font('DejaVuSansCondensed', 'B', 14)
    pdf.ln()
    pdf.cell(0, 10, 'Recommended Career Alignments', ln=1)
    
    for career in career_alignments_data:
        pdf.ln(2)
        
        pdf.set_font('DejaVuSansCondensed', 'B', 12)
        pdf.multi_cell(0, 5, f"{career.name} ({career.match_score:.1f}% Match)")
    
        pdf.set_font('DejaVuSansCondensed', '', 10)
        explanation_plain = re.sub(r'[\*_`]', '', career.explanation)
        pdf.ln() # New line before explanation
        pdf.multi_cell(0, 5, f"Explanation: {explanation_plain}\n")
        
        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.ln() # New line before exams heading
        pdf.multi_cell(0, 5, "Competitive Exams:")
        pdf.set_font('DejaVuSansCondensed', '', 10)
        for exam in career.competitive_exams:
            pdf.ln() # New line for each exam entry
            pdf.multi_cell(0, 5, f"- {exam}")

        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.ln() # New line before degree courses heading
        pdf.multi_cell(0, 5, "Degree Courses:")
        pdf.set_font('DejaVuSansCondensed', '', 10)
        for course in career.degree_courses:
            pdf.ln() # New line for each degree course entry
            pdf.multi_cell(0, 5, f"- {course}")

        pdf.ln(5)

    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.cell(0, 5, 'Clarity and Impact', ln=1)
    pdf.set_font('DejaVuSansCondensed', '', 10)
    clarity_plain = re.sub(r'[\*_`]', '', clarity_and_impact)
    pdf.ln() # New line before clarity content
    pdf.multi_cell(0, 5, clarity_plain)
    pdf.ln(5)

    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 10, 'About the Methodology:') 
    pdf.ln(1)

    concluding_text1 = """
This assessment is grounded in a personality-driven framework. Your responses have been analyzed using associative techniques that map your answers to a defined set of personality traits. These traits are then correlated with specific factors relevant to your academic and career alignment.
    
It is important to recognize that, like any psychometric instrument, a degree of subjectivity and a margin of error may be present. Factors such as the test environment, individual context, and the ever-evolving landscape of education can influence results. To ensure relevance and accuracy, the assessment framework is regularly updated and refined in line with emerging academic standards and technological advancements.
    
The test design incorporates significant contributions from generative AI, which supports the creation, validation, and enhancement of content in accordance with psychometric best practices for reliability and validity.
    """
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 5, concluding_text1.strip())
    pdf.ln(5) 

    pdf.set_font('DejaVuSansCondensed', 'B', 12)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 10, 'Terms & Conditions:') 
    pdf.ln(1)
    
    concluding_text2="""
Disclaimer of Outcome: This assessment is intended solely for informational and guidance purposes. It does not guarantee specific academic, professional, or personal outcomes. The organization does not warrant the accuracy, completeness, or reliability of the information presented in the assessment.
    
Decision-Making Responsibility: Any actions or decisions taken based on this report are entirely the responsibility of the individual participant. The organization bears no responsibility for any direct or indirect consequences resulting from decisions made based on the assessment.
    
Limitation of Liability: Under no circumstances shall the organization be held liable for any direct, indirect, incidental, consequential, or special damages arising from the use or interpretation of the assessment results.
    
Indemnification: By participating in this assessment, you agree to indemnify and hold harmless the organization and its representatives (including officers, employees, and agents) from any claims or liabilities that may arise due to your decisions or actions based on the assessment findings.
    
Scope of Liability: To the fullest extent permitted by applicable law, the organization's liability in relation to this assessment is strictly limited to the amount paid, if any, for access to the assessment.
    
AI-Assisted Design: The assessment’s content and structure have been significantly informed by generative AI technologies. All prompts and processes used adhere to the foundational standards of reliability and validity as required in psychometric assessments.
    
Not a Substitute for Professional Advice: This assessment is not intended to replace expert guidance. Participants are encouraged to consult qualified academic or career professionals before making significant decisions based on the results.
    
Subject to Change: The organization reserves the right to update, modify, suspend, or terminate the assessment or its features at any time, without prior notification.
    
Acknowledgement & Consent: By undertaking this assessment, you acknowledge that your participation is voluntary and that you accept all the terms and conditions stated herein.
    """
    pdf.set_font('DejaVuSansCondensed', '', 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 5, concluding_text2.strip())
    pdf.ln(5) 
    
    try:
        pdf_output = io.BytesIO(pdf.output(dest='S'))
        pdf_output.seek(0)
        return send_file(
            pdf_output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='career_guidance_report.pdf'
        )
    except Exception as e:
        print(f"Error generating PDF: {e}")
        flash("An error occurred while creating the PDF.", 'danger')
        return redirect('/result')

def generate_prompt(session_data: dict) -> str:
    # This is a key function to construct the prompt for the Gemini API
    # based on the user's session data.
    
    answers = session_data.get('assessment_answers', {})
    questions_list = ASSESSMENT_QUESTIONS_RAW.strip().split('\n\n')

    # Use dynamic trait calculation instead of hardcoded scoring
    if answers:
        # Calculate traits dynamically
        top_traits_list = calculate_top_traits(answers, top_n=10)  # Get more traits for AI analysis
        trait_summary = get_trait_summary(answers)
        
        # Create personality summary from calculated traits
        personality_summary = f"Top identified traits: {', '.join(top_traits_list[:5])}"
        if len(top_traits_list) > 5:
            personality_summary += f". Additional traits: {', '.join(top_traits_list[5:])}"
        
        # Add trait frequencies for more detailed analysis
        trait_frequency_info = "; ".join([f"{trait}: {count} occurrences" for trait, count in trait_summary.items()])
        personality_summary += f". Trait frequencies: {trait_frequency_info}"
        
    else:
        # Fallback for when no answers are available
        personality_summary = "Unable to determine traits - no assessment answers available"
    
    graduation_subjects = session_data.get('graduation_subjects', 'None specified')
    preferred_field = session_data.get('preferred_field', 'None specified')
    
    selected_options = "\n".join([
        f"Question {int(idx)+1}: {answer}" 
        for idx, answer in sorted(answers.items(), key=lambda item: int(item[0]))
    ])
    
    prompt = f"""
    You are a career guidance expert for high school students.
    Based on the following information, generate a personalized career suggestion for Indian students in a specific JSON format.
    Also, analyze the assessment answers to determine the student's MBTI personality type. Include the MBTI type, a detailed explanation, and one-word strengths and weaknesses in the output.
    
    ### Student Profile
    - **High School Subjects:** {graduation_subjects}
    - **Calculated Personality Traits:** {personality_summary}
    - **Assessment Answers:**
    {selected_options}
    - **Preferred Career Field (if any):** {preferred_field}
    - **Requested Tone:** Professional

    ### Task
    Provide a JSON object with the following structure. Do not include any text(or code) before or after the JSON object. The JSON should be a single, valid block.

    {{
    "mbti_result": {{
    "type": "ENTJ->The Commander (Extroverted, Intuitive, Thinking, Judging)",
    "explanation": "A detailed explanation (around 400 words) of the MBTI type based on the selected assessment options and calculated traits. This should describe the user's personality traits, preferences, and natural inclinations and the text should use markdown for formatting.",
    "strengths": ["Analytical", "Strategic", "Independent", "Organized", "Focused"],
    "weaknesses": ["Stubborn", "Critical", "Insensitive", "Judgmental", "Overthinking"]
    }},
    "career_alignments": [
    {{
    "name": "CareerName1",
    "match_score": 90.5,
    "explanation": "A detailed explanation (of about 250 words) of why this career is a good fit, linking it to the user's calculated traits and don't use the subjects as the top priority for the suggestion, if a person's traits are matching with a different domain of study then suggest them that as well. This text should use markdown for formatting.",
    "competitive_exams": ["Exam A", "Exam B"],
    "degree_courses": ["Course X", "Course Y"]
    }},
    ... (generate exactly 8 career objects in this list)
    ],
    "clarity_and_impact": "A detailed paragraph explaining the clarity and impact of these career choices, and what the student can expect to achieve at the end of their careers. This text should use markdown for formatting.",
    }}

    The response must be a single, complete JSON object.
    """
    
    return prompt

# --- ADDITIONAL ROUTE FOR DEBUGGING TRAITS ---
@app.route('/debug/traits')
def debug_traits():
    """Debug route to see trait calculation results (remove in production)"""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "No active session"})
    
    session_data = get_session_data(session_id)
    user_answers = session_data.get('assessment_answers', {})
    
    if not user_answers:
        return jsonify({"error": "No assessment answers found"})
    
    top_traits = calculate_top_traits(user_answers, top_n=10)
    trait_summary = get_trait_summary(user_answers)
    
    return jsonify({
        "user_answers": user_answers,
        "top_traits": top_traits,
        "trait_summary": trait_summary
    })

if __name__ == '__main__':
    app.run(debug=True)