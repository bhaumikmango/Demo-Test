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
    1: {'A': 'Logical Reasoning', 'B': 'Creative Expression'},
    2: {'A': 'Organization', 'B': 'Adaptability'},
    3: {'A': 'Empathy', 'B': 'Analytical Thinking'},
    4: {'A': 'Leadership', 'B': 'Supportive Nature'},
    5: {'A': 'Numerical Aptitude', 'B': 'Imaginative Thinking'},
    6: {'A': 'Verbal Communication', 'B': 'Independent Working'},
    7: {'A': 'Accuracy & Diligence', 'B': 'Innovation'},
    8: {'A': 'Technical Curiosity', 'B': 'Emotional Insight'},
    9: {'A': 'Competitive Drive', 'B': 'Teamwork'},
    10: {'A': 'Technical Depth', 'B': 'Artistic Creativity'},
    11: {'A': 'Data-Driven Decision Making', 'B': 'Intuition'},
    12: {'A': 'Leadership', 'B': 'Listening & Empathy'},
    13: {'A': 'Detail Orientation', 'B': 'Curiosity'},
    14: {'A': 'Structure & Discipline', 'B': 'Exploratory Learning'},
    15: {'A': 'Scientific Curiosity', 'B': 'Literary & Dramatic Expression'},
    16: {'A': 'Assertiveness', 'B': 'Reflectiveness'},
    17: {'A': 'Performance Focus', 'B': 'Collaboration'},
    18: {'A': 'Quantitative Analysis', 'B': 'Visual Interpretation'},
    19: {'A': 'Productivity Orientation', 'B': 'Learning Focus'},
    20: {'A': 'Leadership Confidence', 'B': 'Quiet Contribution'},
    21: {'A': 'Technical Problem-Solving', 'B': 'Social Influence'},
    22: {'A': 'Scientific Inquiry', 'B': 'Design Sensibility'},
    23: {'A': 'Stress Tolerance', 'B': 'Adaptability'},
    24: {'A': 'Investigative Mindset', 'B': 'Imaginative Thinking'},
    25: {'A': 'Pragmatism', 'B': 'Expressive Thought'},
    26: {'A': 'Organizational Leadership', 'B': 'Personal Supportiveness'},
    27: {'A': 'Financial Reasoning', 'B': 'Aesthetic Interpretation'},
    28: {'A': 'Technical Confidence', 'B': 'Spontaneous Creativity'},
    29: {'A': 'Process Optimization', 'B': 'Emotional Motivation'},
    30: {'A': 'Focused Independence', 'B': 'Collaborative Engagement'},
    31: {'A': 'Structured Thinking', 'B': 'Exploratory Thinking'},
    32: {'A': 'Routine Orientation', 'B': 'Freedom & Flexibility'},
    33: {'A': 'Precision', 'B': 'Originality'},
    34: {'A': 'Fact-Based Thinking', 'B': 'Emotion-Based Thinking'},
    35: {'A': 'Leadership Assertiveness', 'B': 'Supportive Facilitation'},
    36: {'A': 'Engineering Creativity', 'B': 'Artistic Storytelling'},
    37: {'A': 'Achievement Drive', 'B': 'Helping Orientation'},
    38: {'A': 'Comparative Reasoning', 'B': 'Aesthetic Evaluation'},
    39: {'A': 'Goal Orientation', 'B': 'Curiosity-Driven Exploration'},
    40: {'A': 'Leadership Fulfillment', 'B': 'Supportive Contribution'},
    41: {'A': 'Event Coordination', 'B': 'Conceptual Thinking'},
    42: {'A': 'Analytical Problem Solving', 'B': 'Creative Problem Solving'},
    43: {'A': 'Task Management', 'B': 'Focus & Depth'},
    44: {'A': 'Technological Curiosity', 'B': 'Cultural Awareness'},
    45: {'A': 'Competitiveness', 'B': 'Mentoring & Support'},
    46: {'A': 'Stability Preference', 'B': 'Adaptability'},
    47: {'A': 'Mechanical Aptitude', 'B': 'Emotional Intelligence'},
    48: {'A': 'Efficiency', 'B': 'Inclusivity'},
    49: {'A': 'Academic Learning', 'B': 'Experiential Learning'},
    50: {'A': 'Fact-Based Confidence', 'B': 'People-Based Confidence'},
    51: {'A': 'Technical Innovation', 'B': 'Inspirational Thinking'},
    52: {'A': 'Linear Thinking', 'B': 'Associative Thinking'},
    53: {'A': 'Assertive Leadership', 'B': 'Supportive Role'},
    54: {'A': 'Quantitative Reasoning', 'B': 'Visual Communication'},
    55: {'A': 'Goal Orientation', 'B': 'Exploratory Motivation'},
    56: {'A': 'Scientific Mindset', 'B': 'Artistic Mindset'},
    57: {'A': 'Performance-Driven', 'B': 'Harmony-Seeking'},
    58: {'A': 'Logical Reasoning', 'B': 'Creative Reasoning'},
    59: {'A': 'Oral Expression', 'B': 'Written/Visual Expression'},
    60: {'A': 'Achievement Drive', 'B': 'Collaborative Spirit'}
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
    disclaimer: str

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
A) I enjoy solving puzzles that require logical steps.
B) I like expressing myself through creative writing or art.

A) I always plan my day in advance and stick to schedules.
B) I prefer being flexible and adapting as the day goes on.

A) I often sense what others are feeling, even when they don't say it.
B) I like analyzing situations with facts before drawing conclusions.

A) I enjoy leading group projects and organizing teams.
B) I prefer helping others succeed without being in charge.

A) I feel confident when working with numbers and calculations.
B) I feel confident when designing or imagining new things.

A) I enjoy speaking to groups and persuading others.
B) I enjoy working quietly and independently on tasks.

A) I follow procedures carefully and focus on accuracy.
B) I enjoy improvising and experimenting with new methods.

A) I often find myself thinking about how machines or systems work.                   
B) I often find myself thinking about how people feel or behave.

A) I enjoy competing and striving to be the best.                   
B) I enjoy collaborating and building team spirit.

A) I’m energized by deep technical challenges.                   
B) I’m energized by visual or expressive tasks like art or storytelling.

A) I enjoy reviewing data or evidence to make a decision.                   
B) I enjoy following my instincts or gut feeling when deciding.                   

A) I take initiative and guide others in a group setting.                   
B) I listen carefully and make sure everyone is heard.                   

A) I enjoy fixing errors and paying attention to fine details.                   
B) I enjoy exploring new topics even if I don’t know much about them.                   

A) I prefer having step-by-step instructions.                   
B) I prefer figuring things out through trial and error.                   

A) I like experimenting with ideas in science or technology.                   
B) I like exploring characters and emotions through writing or acting.                   

A) I enjoy debates and expressing clear opinions.                   
B) I enjoy observing and reflecting before sharing thoughts.                   

A) I am energized by competition and measurable goals.                   
B) I am fulfilled by collaboration and shared goals.                   

A) I like interpreting graphs, formulas, or statistics.                   
B) I like interpreting images, stories, or music.                   

A) I focus on results and getting things done efficiently.                   
B) I focus on the process and the experience of learning.                   

A) I feel most confident when I’m in a leadership role.                   
B) I feel most confident when I’m contributing quietly behind the scenes.                   

A) I enjoy coding and building things that solve real-world problems.                   
B) I enjoy engaging people and motivating them through conversation.                   

A) I like working on experiments and discovering how nature works.                   
B) I like designing things that are visually appealing.                   

A) I stay calm and focused even under pressure.                   
B) I adapt quickly to new environments and expectations.                   

A) I prefer investigating facts to understand how things work.                   
B) I prefer imagining possibilities that haven’t been tried before.                   

A) I’m known for being practical and results-driven.                   
B) I’m known for being thoughtful and expressive.                   

A) I enjoy organizing events and managing responsibilities.                   
B) I enjoy helping others one-on-one with emotional support.                   

A) I like comparing financial outcomes and calculating risks.                   
B) I like interpreting the mood and flow of creative works.                   

A) I am confident in working with scientific tools or technologies.                   
B) I am confident when improvising or coming up with spontaneous ideas.                   

A) I feel proud when I optimize systems or improve efficiency.                   
B) I feel proud when I influence or inspire others emotionally.                   

A) I enjoy working independently on long, focused tasks.                   
B) I enjoy collaborating with others in group activities.                   

A) I prefer solving structured problems with clear rules.                   
B) I prefer exploring open-ended questions without right or wrong answers.                   

A) I like following a routine with consistent expectations.                   
B) I like having freedom to choose what and when I do things.                   

A) I enjoy being exact and double-checking my work.                   
B) I enjoy expressing original ideas, even if they’re not perfect.                   

A) I prefer facts and figures over stories and emotions.                   
B) I prefer stories and emotions over facts and figures.                   

A) I take charge when others hesitate.                   
B) I encourage others to speak when they’re hesitant.                   

A) I enjoy developing new technologies or mechanical solutions.                   
B) I enjoy creating performances or artworks that tell stories.                   

A) I am energized by winning and proving my capabilities.                   
B) I am fulfilled when I support someone else's success.                   

A) I like comparing measurable results.                   
B) I like comparing artistic or emotional impacts.                   

A) I set specific goals and track my progress.                   
B) I explore many interests without rigid plans.                   

A) I find satisfaction in being the leader.                   
B) I find satisfaction in helping the leader succeed.                   

A) I enjoy organizing events and coordinating logistics.                   
B) I enjoy exploring big ideas and abstract concepts.                   

A) I prefer solving problems using facts and data.                   
B) I prefer solving problems by imagining new possibilities.                   

A) I enjoy managing multiple responsibilities with precision.                   
B) I enjoy focusing deeply on one meaningful task.                   

A) I get excited when learning about new inventions or technologies.                   
B) I get excited when exploring cultural traditions or histories.                   

A) I enjoy competing in academic or skill-based challenges.                   
B) I enjoy helping others learn and succeed.                   

A) I prefer routines and stable environments.                   
B) I thrive in new and changing situations.                   

A) I enjoy working with machines, tools, or hardware.                   
B) I enjoy working with emotions, stories, or personal growth.                   

A) I focus on completing tasks quickly and correctly.                   
B) I focus on making sure everyone in the group feels included.                                      

A) I like learning from structured lessons or textbooks.                   
B) I like learning from real-life experiences and discovery.                   

A) I feel confident when interpreting facts and data.                   
B) I feel confident when interpreting people and emotions.                   

A) I often come up with ideas to improve systems or tools.                   
B) I often come up with ideas to connect or inspire others.                   

A) I enjoy following a logical process from start to finish.                   
B) I enjoy jumping between ideas and seeing connections.                   

A) I like being in control of outcomes and setting direction.                   
B) I like supporting others and providing backup when needed.                   

A) I enjoy calculating budgets, prices, or quantities.                   
B) I enjoy creating visuals, presentations, or expressive content.                   

A) I prefer clear goals and specific expectations.                   
B) I prefer open-ended projects with space for exploration.                   

A) I enjoy testing hypotheses and drawing conclusions.                   
B) I enjoy exploring stories and expressing emotions.                   

A) I am energized by direct challenges and performance metrics.                   
B) I am energized by group harmony and collective success.                   

A) I analyze problems step by step using logic.                   
B) I approach problems by imagining new angles or creative paths.                   

A) I feel confident in public speaking and presentations.                   
B) I feel confident when I write or express through art.

A) I enjoy competing and setting high personal goals.                   
B) I enjoy collaborating on team projects and celebrating shared wins.
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
    disclaimer = markdown.markdown(suggestion_data.get('disclaimer', ''), extensions=['nl2br'])
    
    raw_suggestion_plain_text = session.get('raw_suggestion_plain_text', '')

    global student_name 
    student_name = session_data.get('student_name', 'Student')

    return render_template(
        'result.html',
        top_traits=top_traits,
        career_alignments=career_alignments,
        clarity_and_impact=clarity_and_impact,
        disclaimer=disclaimer,
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
        disclaimer = validated_data.disclaimer
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
    pdf.ln() # New line before Disclaimer section
    pdf.cell(0, 5, 'Disclaimer', ln=1)
    pdf.set_font('DejaVuSansCondensed', '', 10)
    disclaimer_plain = re.sub(r'[\*_`]', '', disclaimer)
    pdf.ln(5) # New line before disclaimer content
    pdf.multi_cell(0, 5, disclaimer_plain)
    pdf.ln(8)


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
    "type": "INTJ->The Architect (Introverted, Intuitive, Thinking, Judging)",
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
    "disclaimer": "A brief, friendly disclaimer telling the student that their future lies in their hands and this report is just a suggestion and wish them luck for their fruitful future. This text should use markdown for formatting."
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