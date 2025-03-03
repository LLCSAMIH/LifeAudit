from flask import Flask, render_template, request, session, redirect, url_for
import json
import re
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure random key in production

# Parse the life audit framework to extract sections and questions
def parse_audit_framework():
    # Ensure the audit file exists
    if not os.path.exists('audit_framework.txt'):
        create_audit_file()
        
    sections = []
    current_section = None
    current_subsection = None
    questions = []
    
    try:
        with open('audit_framework.txt', 'r') as file:
            lines = file.readlines()
    except FileNotFoundError:
        print("Error: audit_framework.txt not found. Creating file...")
        create_audit_file()
        with open('audit_framework.txt', 'r') as file:
            lines = file.readlines()
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Match main section headers (e.g., "1. DAILY HABITS & ROUTINES")
        section_match = re.match(r'^\s*(\d+)\.\s+([A-Z &]+)$', line)
        if section_match:
            if current_section and questions:
                sections.append({
                    'title': current_section,
                    'subsections': [{
                        'title': current_subsection,
                        'questions': questions
                    }] if current_subsection else [],
                    'questions': questions if not current_subsection else []
                })
            
            current_section = section_match.group(2)
            current_subsection = None
            questions = []
            continue
            
        # Match subsection headers (e.g., "Morning Routine")
        subsection_match = re.match(r'^\s*([A-Za-z ]+)$', line)
        if subsection_match and not line.startswith('-') and not line.startswith('*'):
            if current_subsection and questions and sections:  # Check if sections list is not empty
                if not any(sub['title'] == current_subsection for sub in sections[-1]['subsections']):
                    sections[-1]['subsections'].append({
                        'title': current_subsection,
                        'questions': questions
                    })
                else:
                    for sub in sections[-1]['subsections']:
                        if sub['title'] == current_subsection:
                            sub['questions'].extend(questions)
            
            current_subsection = subsection_match.group(1)
            questions = []
            continue
            
        # Match questions (e.g., "- Wake-up time: __________")
        question_match = re.match(r'^\s*-\s+([^:]+):\s*__+', line)
        if question_match:
            question = question_match.group(1)
            questions.append(question)
            continue
            
        # Special case for nested questions like in Physical Health
        nested_question_match = re.match(r'^\s*\*\s+([^:]+):\s*__+', line)
        if nested_question_match:
            question = nested_question_match.group(1)
            questions.append(f"  • {question}")
            continue
    
    # Add the last section
    if current_section and (questions or current_subsection):
        if current_subsection and questions:
            if not any(section['title'] == current_section for section in sections):
                sections.append({
                    'title': current_section,
                    'subsections': [{
                        'title': current_subsection,
                        'questions': questions
                    }],
                    'questions': []
                })
            else:
                for section in sections:
                    if section['title'] == current_section:
                        section['subsections'].append({
                            'title': current_subsection,
                            'questions': questions
                        })
        else:
            sections.append({
                'title': current_section,
                'subsections': [],
                'questions': questions
            })
    
    # Process reflection questions separately
    reflection_questions = []
    reflection_started = False
    
    for line in lines:
        line = line.strip()
        if 'REFLECTION QUESTIONS' in line:
            reflection_started = True
            continue
        
        if reflection_started and line and line[0].isdigit() and '.' in line:
            question = line.split('.', 1)[1].strip()
            reflection_questions.append(question)
    
    # Flatten all questions for easier navigation
    all_questions = []
    for section in sections:
        for question in section.get('questions', []):
            all_questions.append({
                'section': section['title'],
                'subsection': None,
                'question': question
            })
        
        for subsection in section.get('subsections', []):
            for question in subsection.get('questions', []):
                all_questions.append({
                    'section': section['title'],
                    'subsection': subsection['title'],
                    'question': question
                })
    
    return sections, reflection_questions, all_questions

# Simplified analysis function
def analyze_responses(responses):
    analysis = {
        'strengths': [],
        'weaknesses': [],
        'improvements': []
    }
    
    # Sleep patterns
    sleep_hours = responses.get('Hours spent on sleep (weekly)', '')
    try:
        weekly_sleep = float(sleep_hours)
        daily_sleep = weekly_sleep / 7
        if daily_sleep >= 7 and daily_sleep <= 9:
            analysis['strengths'].append(f"Good sleep habits: You're averaging {daily_sleep:.1f} hours per night.")
        elif daily_sleep < 7:
            analysis['weaknesses'].append(f"Insufficient sleep: You're averaging only {daily_sleep:.1f} hours per night.")
            analysis['improvements'].append("Consider adjusting your schedule to allow for 7-9 hours of sleep nightly.")
    except (ValueError, TypeError):
        pass
    
    # Work-life balance
    work_hours = responses.get('Hours spent working (weekly)', '')
    leisure_hours = responses.get('Hours spent on leisure (weekly)', '')
    try:
        work = float(work_hours) if work_hours else 0
        leisure = float(leisure_hours) if leisure_hours else 0
        
        if work > 50:
            analysis['weaknesses'].append(f"Heavy workload: {work} hours weekly may lead to burnout.")
            analysis['improvements'].append("Set clearer boundaries around work time.")
        
        if leisure < 10:
            analysis['weaknesses'].append("Limited leisure time may affect overall well-being.")
            analysis['improvements'].append("Schedule dedicated time for activities you enjoy.")
        elif leisure >= 20:
            analysis['strengths'].append(f"Prioritizing personal time with {leisure} hours for leisure activities.")
    except (ValueError, TypeError):
        pass
    
    # Financial health
    savings_rate = responses.get('Savings rate (% of income)', '')
    if savings_rate:
        try:
            rate = float(savings_rate.replace('%', '')) if '%' in savings_rate else float(savings_rate)
            if rate >= 20:
                analysis['strengths'].append(f"Excellent savings rate of {rate}%.")
            elif rate >= 15:
                analysis['strengths'].append(f"Healthy savings rate of {rate}%.")
            elif rate > 0:
                analysis['weaknesses'].append(f"Low savings rate of {rate}%.")
                analysis['improvements'].append("Try increasing your savings rate gradually to reach at least 15%.")
        except (ValueError, TypeError):
            pass
    
    # Exercise habits
    exercise_routine = responses.get('Exercise routine', '')
    if exercise_routine:
        if any(word in exercise_routine.lower() for word in ['daily', 'regular', '3', '4', '5', '6', '7']):
            analysis['strengths'].append("Regular exercise routine shows commitment to physical health.")
        elif any(word in exercise_routine.lower() for word in ['none', 'rarely', 'occasional']):
            analysis['weaknesses'].append("Limited physical activity may impact health and energy levels.")
            analysis['improvements'].append("Start with small movement goals like a 10-minute daily walk.")
    
    # Screen time
    screen_time = responses.get('Screen time before bed', '')
    if screen_time and any(word in screen_time.lower() for word in ['hour', 'hours', 'extensive']):
        analysis['weaknesses'].append("Screen time before bed may be affecting sleep quality.")
        analysis['improvements'].append("Consider implementing a digital curfew 1-2 hours before bedtime.")
    
    # Add generic insights if no specific patterns were detected
    if not analysis['strengths']:
        analysis['strengths'].append("Completing this life audit shows commitment to personal growth.")
    
    if not analysis['weaknesses']:
        analysis['weaknesses'].append("Review your responses and identify areas where you feel least satisfied.")
    
    if not analysis['improvements']:
        analysis['improvements'].append("Set SMART goals (Specific, Measurable, Achievable, Relevant, Time-bound).")
        analysis['improvements'].append("Consider regular reviews of your life audit (quarterly or biannually).")
    
    return analysis

# Routes
@app.route('/')
def index():
    return render_template('index.html', page='start')

@app.route('/start_audit', methods=['POST'])
def start_audit():
    # Initialize or reset the session
    session.clear()
    session['responses'] = {}
    session['current_question'] = 0
    
    # Ensure the audit framework file exists
    if not os.path.exists('audit_framework.txt'):
        create_audit_file()
    
    # Parse the audit framework
    sections, reflection_questions, all_questions = parse_audit_framework()
    
    # Ensure we have questions to ask
    if not all_questions:
        # If no questions were parsed, there's an issue with the file format
        create_audit_file()  # Recreate the file with the known format
        sections, reflection_questions, all_questions = parse_audit_framework()
    
    session['all_questions'] = all_questions
    
    return redirect(url_for('question'))

@app.route('/question', methods=['GET', 'POST'])
def question():
    # Get the questions list
    all_questions = session.get('all_questions', [])
    
    if not all_questions:
        # If no questions found, reparse the audit framework
        sections, reflection_questions, all_questions = parse_audit_framework()
        session['all_questions'] = all_questions
    
    # Get current question index
    current_idx = session.get('current_question', 0)
    
    # Process previous answer if this is a POST request
    if request.method == 'POST':
        if current_idx > 0 and current_idx <= len(all_questions):
            previous_question = all_questions[current_idx - 1]['question']
            session['responses'][previous_question] = request.form.get('answer', '')
        
        # Move to the next question
        current_idx += 1
        session['current_question'] = current_idx
    
    # Check if we've reached the end of the questions
    if not all_questions or current_idx >= len(all_questions):
        return redirect(url_for('results'))
    
    # Get the current question
    current_q = all_questions[current_idx]
    
    progress = (current_idx / len(all_questions)) * 100
    
    return render_template('index.html', 
                          page='question',
                          section=current_q['section'],
                          subsection=current_q['subsection'],
                          question=current_q['question'],
                          progress=progress,
                          question_number=current_idx + 1,
                          total_questions=len(all_questions))

@app.route('/results')
def results():
    # Get all responses
    responses = session.get('responses', {})
    
    # Analyze the responses
    analysis = analyze_responses(responses)
    
    return render_template('index.html', 
                          page='results',
                          responses=responses,
                          analysis=analysis)

@app.route('/save_analysis', methods=['POST'])
def save_analysis():
    # Get all responses and analysis
    responses = session.get('responses', {})
    analysis = analyze_responses(responses)
    
    # Combine them into a single dictionary
    data = {
        'responses': responses,
        'analysis': analysis
    }
    
    # Save to a file
    with open('life_audit_results.json', 'w') as file:
        json.dump(data, file, indent=4)
    
    return redirect(url_for('results'))

# Create the audit framework file from the provided text
def create_audit_file():
    audit_text = """COMPREHENSIVE LIFE AUDIT FRAMEWORK

1. DAILY HABITS & ROUTINES

Morning Routine
- Wake-up time: __________
- First activities after waking: __________
- Breakfast habits: __________
- Morning hygiene routine: __________
- Exercise/movement: __________

Daytime Routine
- Work/productive hours: __________
- Breaks (frequency and duration): __________
- Lunch habits: __________
- Hydration habits: __________
- Communication patterns: __________

Evening Routine
- Dinner habits: __________
- Wind-down activities: __________
- Screen time before bed: __________
- Evening hygiene routine: __________
- Bedtime: __________

Weekly Habits
- Exercise (types and frequency): __________
- Social activities: __________
- Household chores: __________
- Leisure activities: __________
- Learning/personal development: __________

2. PERSONAL CARE & HYGIENE PRODUCTS

Bathroom Products
- Shampoo/conditioner: __________ (brand, cost, frequency of purchase)
- Body wash/soap: __________ (brand, cost, frequency of purchase)
- Toothpaste/mouthwash: __________ (brand, cost, frequency of purchase)
- Skincare products: __________ (brand, cost, frequency of purchase)
- Shaving products: __________ (brand, cost, frequency of purchase)

Grooming Products
- Hair products: __________ (brand, cost, frequency of purchase)
- Deodorant: __________ (brand, cost, frequency of purchase)
- Cologne/perfume: __________ (brand, cost, frequency of purchase)
- Makeup (if applicable): __________ (brand, cost, frequency of purchase)
- Other grooming items: __________ (brand, cost, frequency of purchase)

Health Supplements
- Vitamins/minerals: __________ (brand, cost, frequency of purchase)
- Protein/fitness supplements: __________ (brand, cost, frequency of purchase)
- Other supplements: __________ (brand, cost, frequency of purchase)

3. FINANCIAL AUDIT

Income
- Primary income source: __________ (monthly amount)
- Secondary income sources: __________ (monthly amount)
- Passive income: __________ (monthly amount)
- Annual salary/income: __________
- Income growth rate (past 3 years): __________

Fixed Expenses
- Housing (rent/mortgage): __________ (monthly)
- Utilities (electricity, water, gas): __________ (monthly)
- Internet/phone: __________ (monthly)
- Insurance premiums: __________ (monthly)
- Loan payments: __________ (monthly)
- Subscriptions: __________ (monthly)

Variable Expenses
- Groceries: __________ (monthly average)
- Dining out: __________ (monthly average)
- Transportation: __________ (monthly average)
- Entertainment: __________ (monthly average)
- Shopping (non-essential): __________ (monthly average)
- Personal care products: __________ (monthly average)

Savings & Investments
- Emergency fund: __________ (total amount)
- Retirement accounts: __________ (total amount)
- Investment portfolio: __________ (total amount)
- Savings rate (% of income): __________
- Saving goals: __________

Debt
- Credit card debt: __________ (total, interest rate)
- Student loans: __________ (total, interest rate)
- Auto loans: __________ (total, interest rate)
- Mortgage: __________ (total, interest rate)
- Other debt: __________ (total, interest rate)
- Debt-to-income ratio: __________

4. HEALTH & WELLNESS

Physical Health
- Exercise routine: __________
- Recent health metrics (if known):
  * Weight: __________
  * Blood pressure: __________
  * Cholesterol: __________
  * Other relevant metrics: __________
- Last physical exam: __________
- Recurring health issues: __________
- Sleep quality and quantity: __________

Mental Health
- Stress levels (1-10): __________
- Relaxation practices: __________
- Mental health challenges: __________
- Support systems: __________
- Professional support (if any): __________

Nutrition
- Dietary patterns: __________
- Water intake: __________
- Alcohol consumption: __________
- Nutritional challenges: __________
- Food allergies/restrictions: __________

5. RELATIONSHIPS & SOCIAL CONNECTIONS

Close Relationships
- Family connections: __________
- Romantic relationship status: __________
- Close friendships: __________
- Quality time spent with loved ones: __________

Professional Relationships
- Relationship with colleagues: __________
- Relationship with superiors: __________
- Professional network: __________
- Communication skills: __________

Community Connections
- Community involvement: __________
- Volunteer work: __________
- Religious/spiritual community: __________
- Neighborhood connections: __________

6. LIVING ENVIRONMENT

Home
- Current living situation: __________
- Space functionality: __________
- Organization level: __________
- Cleanliness habits: __________
- Areas for improvement: __________

Work Environment
- Work setup: __________
- Ergonomics: __________
- Productivity enablers/barriers: __________
- Commute: __________

7. PERSONAL DEVELOPMENT & GOALS

Career
- Current position: __________
- Career satisfaction (1-10): __________
- Skills being developed: __________
- Career goals (1-year, 5-year): __________
- Professional challenges: __________

Personal Growth
- Books read (past year): __________
- Courses taken: __________
- New skills learned: __________
- Personal challenges overcome: __________
- Areas of interest for development: __________

Life Goals
- Short-term goals (1 year): __________
- Medium-term goals (5 years): __________
- Long-term goals (10+ years): __________
- Legacy considerations: __________
- Purpose/meaning reflections: __________

8. TIME MANAGEMENT

Time Audit
- Hours spent working: __________ (weekly)
- Hours spent on household tasks: __________ (weekly)
- Hours spent on self-care: __________ (weekly)
- Hours spent with loved ones: __________ (weekly)
- Hours spent on leisure: __________ (weekly)
- Hours spent on commuting: __________ (weekly)
- Hours spent on sleep: __________ (weekly)

Time Management Tools
- Calendar system: __________
- To-do list method: __________
- Productivity apps/tools: __________
- Time-wasters identified: __________
- Efficiency opportunities: __________

9. TECHNOLOGY USAGE

Devices
- Smartphone usage: __________ (hours daily)
- Computer usage: __________ (hours daily)
- Television usage: __________ (hours daily)
- Other devices: __________ (hours daily)

Digital Services
- Email management: __________
- Social media usage: __________
- Entertainment subscriptions: __________
- Digital organization: __________
- Digital well-being strategies: __________

10. ACTION PLAN TEMPLATE

Priorities Identified
1. __________
2. __________
3. __________

Short-term Actions (Next 30 Days)
1. __________
2. __________
3. __________

Medium-term Goals (3-6 Months)
1. __________
2. __________
3. __________

Long-term Aspirations (1+ Year)
1. __________
2. __________
3. __________

Accountability System
- Progress tracking method: __________
- Check-in schedule: __________
- Accountability partner: __________
- Rewards system: __________

REFLECTION QUESTIONS

1. What patterns do you notice across different areas of your life?
2. Which areas give you the most satisfaction? Which cause the most stress?
3. Where are your resources (time, money, energy) aligned with your values? Where are they misaligned?
4. What small changes might create the biggest positive impact?
5. What habits would you like to build, and which would you like to break?
6. How does your current life compare to where you'd like to be in 5-10 years?
7. What are you avoiding looking at or addressing?
8. What personal strengths can you leverage to make positive changes?

---

*This framework is designed to be comprehensive but adaptable. Focus on the sections most relevant to your current needs and goals. Regular reviews (quarterly, biannually, or annually) can help track progress and adjust priorities as your life evolves.*"""
    
    with open('audit_framework.txt', 'w') as file:
        file.write(audit_text)

if __name__ == '__main__':
    # Create the audit framework file
    create_audit_file()
    
    # Run the app
    app.run(debug=True)