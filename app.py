import streamlit as st
import base64
import io
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os
import pandas as pd
import re
import matplotlib.pyplot as plt
import pdfplumber  # Pure Python PDF reader
import fitz  # PyMuPDF for PDF-to-image conversion
from io import BytesIO
from pdf2image import convert_from_bytes

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

#======================================================================================================================================================================================

# Prompts
input_prompt1 = """
You are an experienced Technical Human Resource Manager with experience in [JOB_ROLE]. Your task is to review the provided resume against the job description. Provide a *detailed* analysis of the resume, covering the following points:

1. **ATS Score (Percentage Match):** Calculate and provide the percentage match of the resume against the job description.  Be explicit with the percentage.  For example: "ATS Score: 85%"

2. **Missing Keywords:** List any significant keywords from the job description that are missing from the resume.

3. **Missing Skills:** Identify any essential skills mentioned in the job description that are not present in the resume.

4. **Resume Improvement Suggestions:** Offer specific and actionable suggestions on how the resume can be improved to better align with the job description. This could include formatting, content, or keyword optimization.

5. **Skill Improvement Suggestions:** Provide suggestions on how the candidate can improve their skills to meet the job requirements. This could include suggesting relevant courses, projects, or resources.

6. **Relevant Course Links (with Embedded Photos if Applicable):** If possible, provide links to relevant online courses or resources that can help the candidate improve their skills. If the course platform supports image embedding in the description, you can embed the image. If not, don't worry about it.

7. **Overall Remarks:** Provide a concise summary of your overall assessment of the resume and the candidate's fit for the role.  Focus on constructive feedback.  This should *not* be a simple "strengths and weaknesses" summary, but a more nuanced evaluation.

Remember to be detailed and specific in your analysis.  Focus on providing actionable advice that the candidate can use to improve their resume and skills.

give me the 1.ATS Score is visulizations 
            2.missing keywords in highlights
            3.missing skills with highlights
"""
#======================================================================================================================================================================================
input_prompt3 = """
Provide a detailed analysis of the resume, focusing ONLY on the following points:

1. **ATS Score (Percentage Match):** Calculate and provide the percentage match of the resume against the job description. Be explicit with the percentage. For example: "ATS Score: 85%"

2. **Experience:** List and describe the candidate's relevant work experience. Be specific about the roles, responsibilities, and accomplishments. Quantify achievements whenever possible (e.g., "Increased sales by 15%"). If the experience is not directly related to the target job description, explain why it might still be relevant or transferable. If there is no work experience, mention that clearly.

3. **Strengths:** Identify the candidate's key strengths as they relate to the job description. Provide specific examples from the resume to support your assessment. Focus on skills, experience, or qualities that are highly valuable for the role.

4. **Weaknesses:** Point out any areas where the candidate's qualifications could be improved. Be constructive and specific in your feedback. Focus on areas that are relevant to the job description. For example, if the job requires a specific skill that the candidate lacks, mention it. If the resume could be clearer or better organized, provide specific suggestions.

5. **Projects:** Describe any relevant projects the candidate has worked on. Include details about the project's purpose, the candidate's role, and the technologies or skills used. Highlight any significant outcomes or achievements. If there are no projects, mention that clearly.

6. **General Information:** Summarize any other relevant information from the resume that might be of interest, such as awards, publications, or volunteer experience.

7. **Academic Details:** Summarize the candidate's education and qualifications, including degrees, majors, universities, and graduation dates (if available). If academic details are not included, mention that clearly.
"""
#===========================================================================================================================================
def generate_cover_letter(resume_data, job_data, preferences=None):
    """
    Generate a cover letter using Gemini API.
    """
    prompt = f"""
    Write a compelling cover letter for a candidate with the following resume information:

    Applicant Name: {resume_data['name']}
    Contact Information: {resume_data.get('contact', {})}
    Skills: {resume_data['skills']}
    Experience: {resume_data.get('experience', [])} 
    Education: {resume_data.get('education', [])}   
    Summary/Objective: {resume_data.get('summary', '')} 

    They are applying for the following job:

    Job : {job_data['job_title']}
    Company Name: {job_data['company_name']}
    Job Description: {job_data['job_description']}
    Key Requirements/Keywords: {job_data.get('key_requirements', [])}

    Preferences: {preferences or {}}

    Consider the applicant's skills and experience and tailor the cover letter to the specific job description. The cover letter should be professional and persuasive.
    and give only a applicant name not give 'Your name'"""

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text

# Helper functions
def extract_ats_score(response):
    try:
        match = re.search(r"Percentage Match:\s*([\d.]+)%", response)
        if match:
            score_str = match.group(1)
            return float(score_str)
        else:
            return 0.0
    except Exception as e:
        print(f"Error extracting score: {e}")
        return 0.0

#===========================================================================================================================================
def convert_pdf_to_text(pdf_content):
    """Handle both text-based and image-based PDFs using pure Python"""
    try:
        # First try text extraction with pdfplumber
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        if text.strip():
            return text
            
        # If no text, try Gemini Vision for image-based PDFs
        st.warning("The PDF appears to be scanned or image-based. Extracting text using OCR...")
        return extract_text_with_gemini(pdf_content)
        
    except Exception as e:
        st.error(f"PDF processing error: {e}")
        return None

def extract_keywords_missing(response):
    try:
        lines = response.splitlines()
        for line in lines:
            if "Keywords Missing:" in line:
                keywords_missing = line.split(":")[1].strip()
                return keywords_missing
        return "No Keywords Missing"
    except:
        return "Error in keywords missing"
#===========================================================================================================================================
def extract_final_thoughts(response):
    try:
        lines = response.splitlines()
        for line in lines:
            if "Final Thoughts:" in line:
                final_thoughts = line.split(":")[1].strip()
                return final_thoughts
        return "No Final Thoughts"
    except:
        return "Error in final thoughts"
# ===================================================================================================================================================    
def get_gemini_response(prompt, text_data, input_text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt, text_data])
    return response.text
            
def input_pdf_setup(uploaded_file):
    if uploaded_file is not None:
        try:
            # Read PDF bytes
            pdf_bytes = uploaded_file.read()
            
            # Extract text using PyPDF2 (no poppler needed)
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            # If no text extracted (scanned PDF), use pytesseract OCR
            if not text.strip():
                st.warning("PDF appears to be scanned. Trying OCR...")
                try:
                    images = convert_from_bytes(pdf_bytes)  # Fallback (requires poppler)
                    for image in images:
                        text += pytesseract.image_to_string(image) + "\n"
                except:
                    st.error("OCR failed. Please upload a searchable PDF.")
                    return None
            
            return text.strip() if text else None
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return None
    return None
# ============================================================================================================================================================================

def extract_information(response):
    extracted_data = {}
    sections = ["ATS Score", "Experience", "Strengths", "Weaknesses", "Projects", "General Information", "Academic Details"]
    for section in sections:
        match = re.search(rf"\b{section}\s*:\s*(.*?)(?=\b(?:{'|'.join(sections[sections.index(section)+1:] or ['END'])})\b|$)", response, re.DOTALL | re.IGNORECASE)
        if match:
            extracted_data[section] = match.group(1).strip()
        else:
            match = re.search(rf"\b{section}\s*:\s*(.*)", response, re.DOTALL | re.IGNORECASE)  # Fallback regex
            extracted_data[section] = match.group(1).strip() if match else "Not Found"

        if extracted_data[section] == "Not Found":
            extracted_data[section] = "Not Found"

    try:
        ats_score_str = extracted_data.get("ATS Score", "0")
        match = re.search(r"(\d+)%", ats_score_str)
        ats_score = int(match.group(1)) if match else 0
        extracted_data['ATS Score'] = ats_score

    except (ValueError, AttributeError):
        extracted_data['ATS Score'] = 0

    return extracted_data

# =============================================================================================================================================


def generate_gemini_suggestions(linkedin_text, target_skills, job_description):
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Analyze the following LinkedIn profile text against the provided job description and provide detailed suggestions for improvement.

    LinkedIn Profile Text:
    ```
    {linkedin_text}
    ```

    Job Description:
    ```
    {job_description}
    ```
    Target Skills (for context):
    ```
    {", ".join(target_skills)}
    ```

    Focus on these areas in your suggestions:

    * **Skills:** Are the required skills prominently featured and demonstrated?  Are there any missing skills list the skills in numbers format step by step ?
    * **Experience:** Does the experience section effectively showcase relevant experience and accomplishments?  Are the achievements quantified?  How well does it align with the job requirements?
    * **Projects:** Do the projects demonstrate the required skills and experience?  Are they well-described and impactful?
    * **Summary/About:** Does the summary highlight the candidate's qualifications and how they match the job description?  Is it compelling and engaging?
    * **Headline:** Is the headline professional, keyword-rich, and relevant to the target role?
    * **Overall Fit:** How well does the candidate's profile align with the job description overall? What are their strengths and weaknesses?

    Give me the suggestions in a list format, each suggestion starting with a "-". Be specific and actionable.
    """

    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(temperature=0.2))
        suggestions_text = response.text
        suggestions = [s.strip() for s in suggestions_text.splitlines() if s.strip()]
        return suggestions
    except Exception as e:
        st.error(f"Error generating suggestions with Gemini: {e}")
        return []

# =============================================================================================================================================


def analyze_linkedin_text(linkedin_text, target_skills):
    skills_found = set()
    for skill in target_skills:
        if re.search(r"\b" + re.escape(skill) + r"\b", linkedin_text, re.IGNORECASE):
            skills_found.add(skill)

    skill_match_score = (len(skills_found) / len(target_skills)) * 100 if target_skills else 0

    experience_years = 0
    experience_matches = re.findall(r"(?:[0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)\s*of\s*experience", linkedin_text, re.IGNORECASE)
    for match in experience_matches:
        try:
            years = float(match.split()[0])
            experience_years += years
        except ValueError:
            pass

    project_count = len(re.findall(r"(?:project|projects)\b", linkedin_text, re.IGNORECASE))

    education_matches = re.findall(r"(?:Bachelor|Master|PhD|MBA|M.Tech|B.Tech) of (?:[a-zA-Z\s]+)", linkedin_text, re.IGNORECASE)
    degrees = [match.strip() for match in education_matches]

    return {
        "skill_match_score": skill_match_score,
        "skills_found": list(skills_found),
        "experience_years": experience_years,
        "project_count": project_count,
        "degrees": degrees,
    }

# =============================================================================================================================================

def extract_industries_from_resume(resume_text):
    """
    Extracts relevant industries from the resume text.

    Args:
        resume_text (str): The text content of the resume.

    Returns:
        list: A list of industries mentioned in the resume.
    """

    # Placeholder - Replace with your industry extraction logic
    industries = re.findall(r"\b(Software|Data Science|Web Development|Finance|Healthcare|Education)\b", resume_text, re.IGNORECASE)  # Example industries
    return list(set(industries))
# =============================================================================================================================================


def get_job_postings(skills, industries=None, num_jobs=10):  # Replace with your actual data source
    """
    Retrieves job postings based on skills and industries.

    Args:
        skills (list): A list of skills to search for.
        industries (list, optional): A list of industries to filter by. Defaults to None.
        num_jobs (int, optional): The maximum number of jobs to retrieve. Defaults to 10.

    Returns:
        list: A list of dictionaries, where each dictionary represents a job posting.
              Each job posting should at least have 'title', 'company', 'description', 'link', 'industry' (if available).
    """

    # Placeholder - Replace with your actual job data retrieval logic (API, dataset, etc.)
    # Example using a dummy dataset:
    dummy_jobs = [
        {"title": "Software Engineer", "company": "Tech Co.", "description": "...", "link": "...", "industry": "Software"},
        {"title": "Data Scientist", "company": "Data Inc.", "description": "...", "link": "...", "industry": "Data Science"},
        {"title": "Web Developer", "company": "Web Solutions", "description": "...", "link": "...", "industry": "Web Development"},
        # ... more dummy jobs
    ]

    # Filter by industry if provided
    filtered_jobs = dummy_jobs if industries is None else [
        job for job in dummy_jobs if job["industry"] in industries
    ]

    # Filter by skills (simple keyword matching for now)
    skill_matched_jobs = []
    for job in filtered_jobs:
        for skill in skills:
            if skill.lower() in job["description"].lower(): # Simple keyword matching
                skill_matched_jobs.append(job)
                break # only add job once if it matches multiple skills.

    return skill_matched_jobs[:num_jobs]  # Return up to num_jobs

# =============================================================================================================================================

def extract_skills_from_resume(resume_text):
    """
    Extracts skills from the resume text using Gemini or other methods.
    (Adapt this to use your existing resume parsing logic or Gemini if needed)

    Args:
        resume_text (str): The text content of the resume.

    Returns:
        list: A list of skills extracted from the resume.
    """
    # Placeholder - Replace with your resume parsing logic
    # Example (using regex - improve as needed):
    skills = re.findall(r"\b(Python|Java|C++|SQL|Machine Learning|Deep Learning|Data Analysis|Communication|Project Management)\b", resume_text, re.IGNORECASE)
    return list(set(skills))  # Remove duplicates

# =============================================================================================================================================

# Function to extract text from PDF
def convert_pdf_to(pdf_content):
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_content))  # Use pypdf's PdfReader
        text = ""
        for page in pdf_reader.pages:
            try:  # Handle potential issues with individual pages
                page_text = page.extract_text()  # Use pypdf's extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                st.warning(f"Error extracting text from a page: {e}")  # Warn but continue
                continue  # Skip to the next page

        if not text.strip():  # If no text extracted, try OCR
            st.warning("The PDF appears to be scanned or image-based. Extracting text using OCR...")
            images = convert_from_bytes(pdf_content)
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"

        return text.strip() if text else None

    except Exception as e:  # Catch any pypdf-related errors
        st.error(f"Error reading or processing PDF: {e}. Please check if the file is valid and not encrypted.")
        return None


# Function to extract skills from resume text
def extract_skills_from(resume_text):
    
    skills_list = [
    "Python", "Java", "C++", "SQL", "Machine Learning", "Data Analysis",
    "Project Management", "Communication", "AWS", "Azure", "JavaScript",
    "React", "Angular", "DevOps", "Docker", "Kubernetes", "Git", "Agile",
    "Scrum", "Tableau", "Power BI", "Excel", "R", "TensorFlow", "PyTorch",
    "Deep Learning", "Natural Language Processing", "Computer Vision",
    "HTML", "CSS", "Node.js", "Django", "Flask", "MongoDB", "Big Data",
    "Hadoop", "Spark", "NoSQL", "Linux", "Cybersecurity", "Ethical Hacking",
    "UI/UX Design", "Figma", "Adobe XD", "Solidity", "Smart Contracts",
    "Blockchain", "Cloud Architecture", "Data Warehousing", "Microservices",
    "RESTful APIs", "GraphQL", "Automation", "Selenium", "Quality Assurance",
    "Robotics", "IoT", "Embedded Systems", "MATLAB", "AutoCAD", "Product Management",
    "Digital Marketing", "SEO", "Content Marketing", "Social Media Management",
    "Business Analysis", "Financial Modeling", "ERP", "Supply Chain Management",
    "Renewable Energy", "3D Modeling", "Game Development", "Unity", "Unreal Engine"
]

    skills_found = []
    for skill in skills_list:
        if re.search(r"\b" + re.escape(skill) + r"\b", resume_text, re.IGNORECASE):
            skills_found.append(skill)
    return skills_found

# Function to suggest job roles based on skills
def suggest_job_roles(skills):
   
    job_roles = {
    "Data Scientist": ["Python", "Machine Learning", "Data Analysis", "SQL", "R"],
    "Software Engineer": ["Python", "Java", "C++", "JavaScript", "Git"],
    "DevOps Engineer": ["AWS", "Azure", "Docker", "Kubernetes", "Git"],
    "Project Manager": ["Project Management", "Communication", "Agile", "Scrum"],
    "Business Analyst": ["Excel", "Tableau", "Power BI", "SQL", "Communication"],
    "Machine Learning Engineer": ["Python", "Machine Learning", "TensorFlow", "PyTorch"],
    "Web Developer": ["JavaScript", "React", "Angular", "Python", "SQL"],
    "AI Engineer": ["Python", "Deep Learning", "NLP", "PyTorch", "TensorFlow"],
    "Cloud Engineer": ["AWS", "Azure", "Google Cloud", "Docker", "Linux"],
    "Cybersecurity Analyst": ["Network Security", "Ethical Hacking", "Firewalls", "Python"],
    "Full Stack Developer": ["JavaScript", "React", "Node.js", "MongoDB", "SQL"],
    "Data Engineer": ["SQL", "Python", "Big Data", "Spark", "Hadoop"],
    "Database Administrator": ["SQL", "PostgreSQL", "MySQL", "MongoDB", "Data Security"],
    "Network Engineer": ["Networking", "Cisco", "Routing", "Switching", "Firewall"],
    "Embedded Systems Engineer": ["C", "C++", "RTOS", "Microcontrollers", "IoT"],
    "Electrical Engineer": ["Circuit Design", "MATLAB", "AutoCAD", "Power Systems"],
    "Mechanical Engineer": ["SolidWorks", "AutoCAD", "MATLAB", "Thermodynamics"],
    "Robotics Engineer": ["Python", "ROS", "Automation", "Computer Vision"],
    "Automation Engineer": ["PLC", "SCADA", "Python", "IoT", "Control Systems"],
    "Data Analyst": ["SQL", "Python", "Excel", "Power BI", "Statistics"],
    "BI Analyst": ["Power BI", "Tableau", "SQL", "Data Visualization"],
    "UI/UX Designer": ["Figma", "Adobe XD", "Sketch", "User Research"],
    "IT Support Specialist": ["Troubleshooting", "Windows", "Linux", "Networking"],
    "Quality Assurance Engineer": ["Selenium", "JIRA", "Testing", "Automation"],
    "Game Developer": ["Unity", "Unreal Engine", "C#", "C++", "Blender"],
    "System Administrator": ["Linux", "Windows Server", "Networking", "Cloud"],
    "IT Consultant": ["Business Analysis", "Networking", "Cybersecurity", "Cloud"],
    "Blockchain Developer": ["Solidity", "Ethereum", "Smart Contracts", "Web3.js"],
    "Product Manager": ["Product Strategy", "Market Research", "Agile"],
    "HR Analyst": ["HR Analytics", "Excel", "Communication", "Recruitment"],
    "SEO Specialist": ["SEO", "Google Analytics", "Keyword Research", "Content Marketing"],
    "Digital Marketing Manager": ["Google Ads", "Social Media Marketing", "SEO"],
    "Frontend Developer": ["HTML", "CSS", "JavaScript", "React", "Vue.js"],
    "Backend Developer": ["Node.js", "Django", "Flask", "SQL", "MongoDB"],
    "DevSecOps Engineer": ["Security Compliance", "Threat Modeling", "AWS"],
    "Ethical Hacker": ["Penetration Testing", "Metasploit", "Wireshark", "Cybersecurity"],
    "Finance Analyst": ["Excel", "Financial Modeling", "SQL", "Python", "Tableau"],
    "Biomedical Engineer": ["MATLAB", "Bioinformatics", "Medical Imaging", "Python"],
    "Supply Chain Analyst": ["Supply Chain Management", "ERP", "SAP", "Excel"],
    "Renewable Energy Engineer": ["Solar Energy", "Wind Power", "Energy Storage"],
    "AR/VR Developer": ["Unity", "C#", "3D Modeling", "Oculus SDK"],
    "IoT Engineer": ["Raspberry Pi", "Arduino", "Embedded Systems", "Python", "MQTT"],
    "Legal Consultant": ["Corporate Law", "Legal Research", "Compliance", "Contracts"],
    "Content Writer": ["SEO Writing", "Content Strategy", "Copywriting", "Editing"],
    "Graphic Designer": ["Adobe Photoshop", "Illustrator", "Canva", "UI Design"],
    "Cyber Forensics Analyst": ["Digital Forensics", "Cyber Law", "Encryption", "Malware Analysis"],
    "Operations Manager": ["Supply Chain", "Logistics", "Inventory Management", "Lean Six Sigma"]
}

    
    # Calculate priority order based on skill match
    role_priority = {}
    for role, required_skills in job_roles.items():
        match_count = sum(1 for skill in required_skills if skill in skills)
        role_priority[role] = match_count
    
    # Sort roles by priority (highest match first)
    sorted_roles = sorted(role_priority.items(), key=lambda x: x[1], reverse=True)
    return [role for role, _ in sorted_roles]

# Function to suggest trending technologies
def suggest_trending_technologies():
    """
    Returns a list of trending technologies.
    """
    return [
    "Artificial Intelligence (AI)",
    "Machine Learning (ML)",
    "Deep Learning",
    "Natural Language Processing (NLP)",
    "Computer Vision",
    "Blockchain",
    "Internet of Things (IoT)",
    "Cloud Computing (AWS, Azure, GCP)",
    "DevOps",
    "Cybersecurity",
    "Data Science",
    "Big Data",
    "Quantum Computing",
    "5G Technology",
    "Augmented Reality (AR) / Virtual Reality (VR)",
    "Edge Computing",
    "Robotic Process Automation (RPA)",
    "Autonomous Vehicles",
    "Digital Twins",
    "Extended Reality (XR)",
    "Smart Cities",
    "5G/6G Networks",
    "Biotechnology",
    "Nanotechnology",
    "Mixed Reality",
    "Wearable Technology",
    "Serverless Computing",
    "Microservices Architecture",
    "Voice Assistants & Conversational AI",
    "Predictive Analytics",
    "Industry 4.0",
    "Cyber-Physical Systems"
]


# Function to suggest online courses
def suggest_online_courses(job_role):
    """
    Suggests online courses based on the job role.
    """
    courses = {
    "Data Scientist": [
        "Data Science Specialization by Coursera",
        "Machine Learning by Andrew Ng (Coursera)",
        "Python for Data Science (Udemy)",
        "Data Science with R (edX)",
        "Data Science Bootcamp (Springboard)"
    ],
    "Software Engineer": [
        "The Complete Python Bootcamp (Udemy)",
        "Java Programming Masterclass (Udemy)",
        "Full-Stack Web Development (Udemy)",
        "C++ for Programmers (Udacity)",
        "Advanced Data Structures in Java (Coursera)"
    ],
    "DevOps Engineer": [
        "AWS Certified Solutions Architect (Udemy)",
        "Docker Mastery (Udemy)",
        "Kubernetes for Beginners (Udemy)",
        "DevOps on AWS (Coursera)",
        "CI/CD Pipelines with Jenkins (Udemy)"
    ],
    "Project Manager": [
        "PMP Certification Training (Udemy)",
        "Agile Project Management (Coursera)",
        "Scrum Master Certification (Udemy)",
        "PRINCE2 Foundation & Practitioner (Udemy)",
        "Kanban for Agile Teams (LinkedIn Learning)"
    ],
    "Business Analyst": [
        "Tableau Training for Beginners (Udemy)",
        "Power BI Essentials (Udemy)",
        "Excel for Business Analysts (Udemy)",
        "SQL for Business Analysts (Coursera)",
        "Business Analysis Fundamentals (Udemy)"
    ],
    "Machine Learning Engineer": [
        "Deep Learning Specialization by Andrew Ng (Coursera)",
        "TensorFlow Developer Certificate (Coursera)",
        "PyTorch for Deep Learning (Udemy)",
        "Applied AI with DeepLearning (edX)",
        "ML & AI Specialization (Udacity)"
    ],
    "Web Developer": [
        "The Complete JavaScript Course (Udemy)",
        "React - The Complete Guide (Udemy)",
        "Angular - The Complete Guide (Udemy)",
        "Node.js and Express (Coursera)",
        "Full-Stack Web Development (Udacity)"
    ],
    "Cloud Engineer": [
        "AWS Certified Cloud Practitioner (Udemy)",
        "Google Cloud Associate Engineer (Coursera)",
        "Azure Fundamentals (Microsoft Learn)",
        "Cloud Computing Specialization (edX)",
        "Kubernetes in Google Cloud (Coursera)"
    ],
    "Cybersecurity Analyst": [
        "Certified Ethical Hacker (CEH) (Udemy)",
        "Cybersecurity Fundamentals (Coursera)",
        "Network Security Essentials (edX)",
        "CompTIA Security+ Certification (Udemy)",
        "SOC Analyst Training (LinkedIn Learning)"
    ],
    "Full Stack Developer": [
        "Full Stack Development Bootcamp (Udemy)",
        "MERN Stack Course (Udemy)",
        "Django and React (Udemy)",
        "GraphQL for Beginners (Coursera)",
        "Advanced Web Development (LinkedIn Learning)"
    ],
    "Data Engineer": [
        "Data Engineering with Google Cloud (Coursera)",
        "Big Data with Spark and Hadoop (edX)",
        "ETL Pipelines with SQL (Udemy)",
        "Data Warehousing for Beginners (Udacity)",
        "Apache Airflow for Data Engineering (Udemy)"
    ],
    "Database Administrator": [
        "SQL for Database Administrators (Udemy)",
        "MySQL Database Administration (Coursera)",
        "PostgreSQL for Beginners (Udemy)",
        "MongoDB University (MongoDB Official)",
        "Oracle Database Administration (Udemy)"
    ],
    "AI Engineer": [
        "Artificial Intelligence Specialization (Coursera)",
        "Advanced AI for Developers (Udacity)",
        "Generative AI with Transformers (Udemy)",
        "NLP with Python and SpaCy (Udemy)",
        "Self-Driving Cars and AI (Udacity)"
    ],
    "Embedded Systems Engineer": [
        "Embedded C Programming (Udemy)",
        "RTOS for Embedded Systems (Udemy)",
        "Microcontroller Programming (Coursera)",
        "IoT & Embedded Systems (edX)",
        "ARM Cortex Programming (Udemy)"
    ],
    "Blockchain Developer": [
        "Blockchain Basics (Coursera)",
        "Ethereum and Solidity (Udemy)",
        "Hyperledger Fabric for Developers (edX)",
        "Smart Contracts Development (Udemy)",
        "Bitcoin and Cryptography (Udacity)"
    ],
    "Game Developer": [
        "Unity Game Development (Udemy)",
        "Unreal Engine for Beginners (Udemy)",
        "C# for Game Developers (Coursera)",
        "Blender for 3D Modeling (Udemy)",
        "VR Game Development (Udacity)"
    ],
    "IoT Engineer": [
        "Internet of Things (IoT) Fundamentals (Coursera)",
        "IoT with Raspberry Pi (Udemy)",
        "Embedded IoT Security (Udemy)",
        "MQTT Protocols for IoT (LinkedIn Learning)",
        "IoT Edge Computing (edX)"
    ],
    "Robotics Engineer": [
        "Introduction to Robotics (Coursera)",
        "ROS for Beginners (Udemy)",
        "Autonomous Robots and Path Planning (Udacity)",
        "Computer Vision for Robotics (edX)",
        "Humanoid Robotics (Udemy)"
    ],
    "Digital Marketing Specialist": [
        "Google Ads Certification (Google Skillshop)",
        "SEO Mastery Course (Udemy)",
        "Social Media Marketing (Coursera)",
        "Content Marketing Strategy (HubSpot Academy)",
        "Google Analytics Certification (Google Skillshop)"
    ],
    "UI/UX Designer": [
        "UI/UX Design Specialization (Coursera)",
        "Adobe XD and Figma for UX Design (Udemy)",
        "Human-Computer Interaction (Udacity)",
        "Prototyping for UX (LinkedIn Learning)",
        "UX Research Methods (Udemy)"
    ],
    "Finance Analyst": [
        "Financial Analysis and Modeling (Coursera)",
        "Excel for Financial Analysis (Udemy)",
        "Stock Market Investing (Udemy)",
        "Python for Finance (edX)",
        "Accounting and Financial Statement Analysis (Udacity)"
    ],
    "Operations Manager": [
        "Supply Chain Analytics (Coursera)",
        "Lean Six Sigma for Operations (Udemy)",
        "Business Process Improvement (LinkedIn Learning)",
        "ERP Systems and Implementation (Udacity)",
        "Operations Management (edX)"
    ]


    }
    return courses.get(job_role, ["No specific courses found for this role."])


def suggest_salary_expectations(job_role):
    """
    Suggests salary expectations based on the job role.
    """
    salaries = {
    "Data Scientist": "$80,000 - $120,000",
    "Software Engineer": "$70,000 - $110,000",
    "DevOps Engineer": "$90,000 - $130,000",
    "Project Manager": "$85,000 - $120,000",
    "Business Analyst": "$60,000 - $90,000",
    "Machine Learning Engineer": "$95,000 - $140,000",
    "Web Developer": "$50,000 - $90,000",
    "AI Engineer": "$100,000 - $150,000",
    "Cloud Engineer": "$90,000 - $140,000",
    "Cybersecurity Analyst": "$80,000 - $130,000",
    "Full Stack Developer": "$75,000 - $120,000",
    "Data Engineer": "$85,000 - $130,000",
    "Database Administrator": "$70,000 - $110,000",
    "Network Engineer": "$65,000 - $105,000",
    "Embedded Systems Engineer": "$75,000 - $115,000",
    "Electrical Engineer": "$70,000 - $100,000",
    "Mechanical Engineer": "$65,000 - $95,000",
    "Robotics Engineer": "$80,000 - $125,000",
    "Automation Engineer": "$75,000 - $115,000",
    "Data Analyst": "$55,000 - $85,000",
    "BI Analyst": "$65,000 - $95,000",
    "UI/UX Designer": "$60,000 - $100,000",
    "IT Support Specialist": "$45,000 - $75,000",
    "Quality Assurance Engineer": "$60,000 - $95,000",
    "Game Developer": "$65,000 - $110,000",
    "System Administrator": "$60,000 - $100,000",
    "IT Consultant": "$75,000 - $120,000",
    "Blockchain Developer": "$90,000 - $150,000",
    "Product Manager": "$90,000 - $140,000",
    "HR Analyst": "$55,000 - $85,000",
    "SEO Specialist": "$50,000 - $85,000",
    "Digital Marketing Manager": "$70,000 - $110,000"
    }

    return salaries.get(job_role, "Salary data not available for this role.")

# Streamlit app
st.set_page_config(page_title="RezumeX", page_icon=":page_facing_up:", layout="wide")
st.markdown(
    """
    <style>
    .stButton {
        display: flex;
        justify-content: center; /* Centers the button horizontally */
    }
    .stButton > button {
        width: 100%; /* Make buttons fill the container width */
        max-width: 600px; /* Set a maximum width (adjust as needed) */
        height: auto !important; /* Make button height adjust to text */
        min-height: 60px; /* Set a minimum height */
        font-size: 4 rem; /* Increase font size (slightly bigger) */
        font-weight: bold; /* Make text bold */
        color: #FFFFFF; /* White text color */
        padding: 15px 30px; /* Add padding */
        margin-bottom: 10px; /* Add some spacing between buttons */
        background: linear-gradient(to right, #8A2BE2, #E6C9FC); /* Example gradient */
        border: none;
        border-radius: 8px;
        cursor: pointer;
        text-align: center; /* Center text within the button */
        word-wrap: break-word; /* Allow text to wrap within the button */
    }

    body {
        background-image: url("https://www.google.com/url?sa=i&url=https%3A%2F%2Fpngtree.com%2Ffreebackground%2Fblue-and-purple-modern-background-design-free-png_1451507.html&psig=AOvVaw3FYlsL3xFuLzKbD5XhnUNS&ust=1740228863976000&source=images&cd=vfe&opi=89978449&ved=0CBEQjRxqFwoTCNCOnOzn1IsDFQAAAAAdAAAAABAJ"); /* Replace with your image URL */
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    .main .block-container {
        background-color: rgba(255, 255, 255, 0.8);
        padding: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
#===========================================================================================================================================

# Initialize session state for user type
if "user_type" not in st.session_state:
    st.session_state.user_type = "welcome"
def set_user_type(user_type):
    st.session_state.user_type = user_type

#================================================================================================================================================================
job_roles = [
    "Software Engineer",
    "Data Scientist",
    "Machine Learning Engineer",
    "AI Researcher",
    "Cybersecurity Analyst",
    "Cloud Engineer",
    "DevOps Engineer",
    "Database Administrator",
    "Web Developer",
    "Mobile App Developer",
    "IT Support Specialist",
    "Network Engineer",
    "Game Developer",
    "Blockchain Developer",
    "UI/UX Designer",
    "Product Manager (Tech)",
    "Business Intelligence Analyst",
    "Data Engineer",
    "Computer Vision Engineer",
    "Project Manager",
    "Business Analyst",
    "Operations Manager",
    "Product Manager",
    "Human Resources Manager",
    "Recruitment Specialist",
    "Training and Development Manager",
    "Office Administrator",
    "Management Consultant",
    "Supply Chain Manager",
    "Logistics Coordinator",
    "Quality Assurance Manager",
    "Risk Manager",
    "Procurement Specialist",
    "Marketing Manager",
    "Digital Marketing Specialist",
    "SEO Specialist",
    "Content Strategist",
    "Social Media Manager",
    "Brand Manager",
    "Sales Representative",
    "Account Manager",
    "Public Relations Specialist",
    "Affiliate Marketing Manager",
    "E-commerce Manager",
    "Advertising Manager",
    "Customer Service Representative",
    "Call Center Agent",
    "Customer Success Manager",
    "Help Desk Support",
    "Technical Support Engineer",
    "Client Relations Manager",
    "Financial Analyst",
    "Investment Banker",
    "Accountant",
    "Auditor",
    "Tax Consultant",
    "Risk Analyst",
    "Actuary",
    "Bookkeeper",
    "Finance Manager",
    "Chief Financial Officer (CFO)",
    "Doctor",
    "Nurse",
    "Pharmacist",
    "Medical Lab Technician",
    "Radiologist",
    "Dentist",
    "Surgeon",
    "Physical Therapist",
    "Psychologist",
    "Veterinarian",
    "Healthcare Administrator",
    "Biomedical Engineer",
    "Nutritionist",
    "Paramedic",
    "Teacher",
    "Professor",
    "Tutor",
    "Curriculum Developer",
    "Instructional Designer",
    "Librarian",
    "Education Consultant",
    "Training Coordinator",
    "Mechanical Engineer",
    "Electrical Engineer",
    "Civil Engineer",
    "Structural Engineer",
    "Aerospace Engineer",
    "Automotive Engineer",
    "Chemical Engineer",
    "Environmental Engineer",
    "Industrial Engineer",
    "Mechatronics Engineer",
    "Robotics Engineer",
    "Manufacturing Engineer",
    "Petroleum Engineer",
    "Marine Engineer",
    "Lawyer",
    "Paralegal",
    "Legal Consultant",
    "Corporate Counsel",
    "Compliance Officer",
    "Judge",
    "Mediator",
    "Graphic Designer",
    "Video Editor",
    "Animator",
    "Illustrator",
    "Photographer",
    "Content Writer",
    "Journalist",
    "Editor",
    "Fashion Designer",
    "Interior Designer",
    "Event Planner",
    "Music Producer",
    "Film Director",
    "Research Scientist",
    "Biotechnologist",
    "Pharmacologist",
    "Data Analyst",
    "Statistician",
    "Geologist",
    "Astronomer",
    "Environmental Scientist",
    "Chemist",
    "Physicist",
    "Hotel Manager",
    "Chef",
    "Travel Agent",
    "Tour Guide",
    "Event Coordinator",
    "Concierge",
    "Bartender",
    "Flight Attendant",
    "Electrician",
    "Plumber",
    "Carpenter",
    "Welder",
    "Mechanic",
    "Construction Worker",
    "HVAC Technician",
    "Truck Driver",
    "Painter",
    "Entrepreneur",
    "Real Estate Agent",
    "Security Officer",
    "Social Worker",
    "Politician",
    "Police Officer",
    "Firefighter",
    "Military Officer",
    "Athlete",
    "Coach",
    "Fitness Trainer",
    "Zookeeper"
]

#===========================================================================================================================================

# Conditional Page Display
if st.session_state.user_type == "welcome":
    # Welcome Page
    st.markdown("<h1 class='welcome-text'>Welcome To Rezume✘ </h1>", unsafe_allow_html=True)
    st.markdown("<p class='app-description'>Application Tracking System</p>", unsafe_allow_html=True)

    # User Type Buttons
    st.markdown("<div class='user-buttons'>", unsafe_allow_html=True)
    if st.button("User (with Job Role)", use_container_width=False):
        set_user_type("user_with_job_role")
    if st.button("User (without Job Role)", use_container_width=False):
        set_user_type("general_user")
    if st.button("HR", use_container_width=False):
        set_user_type("hr")
    if st.button("Linkedin Analyser ", use_container_width=False):
        set_user_type("linkedin")
    if st.button("Cover Letter Generator", use_container_width=False):
        set_user_type("cover_letter_generator")
    st.markdown("</div>", unsafe_allow_html=True)

    # Welcome Content
    st.markdown("<div class='welcome-content'>", unsafe_allow_html=True)
    st.subheader("🔥 Unlock Your Potential with RezumeX")
    st.write("🚀 RezumeX empowers you to take control of your career journey. Whether you're a seasoned professional or just starting out, our powerful ATS helps you create a resume that stands out and gets noticed by recruiters.")
    st.write("🚀 For **job seekers with a specific role in mind**, our tailored analysis ensures your resume aligns perfectly with the target position. We highlight your relevant skills and experience, maximizing your chances of landing an interview.")
    st.write("🚀 For **job seekers exploring different options**, RezumeX provides valuable insights into your strengths and areas for improvement. Discover your potential and identify the roles that best match your skills and aspirations.")
    st.write("🚀 For **HR professionals**, RezumeX simplifies the tedious task of resume screening. Quickly identify top candidates, assess their qualifications, and make data-driven hiring decisions.")
    st.markdown("</div>", unsafe_allow_html=True)
#=======================================================================================================================================================================================================================================================
elif st.session_state.user_type == "hr":
    st.title("📊 HR Dashboard")
    st.markdown("---")
    
    # Input Section
    col1, col2 = st.columns(2)
    with col1:
        input_text = st.text_area("✍️ Enter Job Description:", height=250)
    with col2:
        uploaded_files = st.file_uploader("📤 Upload Resumes (PDFs)", 
                                        type=["pdf"], 
                                        accept_multiple_files=True)
    
    if st.button("🏠 Back to Home"):
        set_user_type("welcome")

    if uploaded_files and input_text:
        st.success(f"✅ {len(uploaded_files)} resumes uploaded for analysis")
        
        if st.button("🔍 Analyze Resumes", type="primary"):
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # Update progress
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)
                    status_text.text(f"Analyzing {i+1}/{len(uploaded_files)}: {uploaded_file.name[:30]}...")
                    
                    # Process resume
                    resume_text = input_pdf_setup(uploaded_file)
                    if not resume_text:
                        st.warning(f"Skipped {uploaded_file.name}: No text extracted")
                        continue
                    
                    # Get analysis from Gemini
                    response = get_gemini_response(
                        prompt=input_prompt3,
                        text_data=resume_text,
                        input_text=input_text
                    )
                    
                    # Extract structured information
                    extracted_info = extract_information(response)
                    extracted_info["Filename"] = uploaded_file.name
                    all_results.append(extracted_info)
                    
                except Exception as e:
                    st.error(f"❌ Error analyzing {uploaded_file.name}: {str(e)}")
            
            progress_bar.empty()
            status_text.empty()
            
            if not all_results:
                st.error("No valid results generated")
            return
                
            # Process and display results
            df = pd.DataFrame(all_results)
            
            # Sort by ATS Score (descending)
            if 'ATS Score' in df.columns:
                df.sort_values('ATS Score', ascending=False, inplace=True)
                
                # Visualizations
                st.markdown("---")
                st.subheader("📈 Analysis Summary")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Top Candidate Score", 
                             f"{df['ATS Score'].max()}%",
                             delta=f"{df['ATS Score'].mean():.1f}% avg")
                    
                    fig1 = plt.figure()
                    plt.hist(df['ATS Score'], bins=10, color='skyblue', edgecolor='black')
                    plt.xlabel("ATS Score (%)")
                    plt.ylabel("Number of Candidates")
                    st.pyplot(fig1)
                
                with col2:
                    st.metric("Candidates Analyzed", 
                             len(df),
                             delta=f"{len(uploaded_files) - len(df)} failed")
                    
                    fig2 = plt.figure()
                    df['ATS Score'].plot(kind='box', vert=False)
                    plt.xlabel("ATS Score Distribution")
                    st.pyplot(fig2)
                
                # Detailed Results
                st.markdown("---")
                st.subheader("📋 Candidate Breakdown")
                
                # Interactive filtering
                min_score = st.slider("Filter by minimum ATS score", 
                                     min_value=0, 
                                     max_value=100,
                                     value=50)
                
                filtered_df = df[df['ATS Score'] >= min_score]
                st.dataframe(filtered_df.style.highlight_max(subset=['ATS Score'], color='lightgreen'),
                           use_container_width=True)
                
                # Individual candidate details
                st.markdown("---")
                st.subheader("🧑‍💼 Candidate Details")
                
                selected_file = st.selectbox("Select candidate to view details:",
                                           filtered_df['Filename'])
                
                if selected_file:
                    candidate_data = df[df['Filename'] == selected_file].iloc[0]
                    with st.expander(f"Full analysis for {selected_file}"):
                        for key, value in candidate_data.items():
                            if key != 'Filename':
                                st.markdown(f"**{key}**: {value}")
            
            else:
                st.warning("No ATS scores were extracted from the analysis")

    elif not input_text and uploaded_files:
        st.warning("⚠️ Please enter a job description")
    elif not uploaded_files and input_text:
        st.warning("⚠️ Please upload resumes")
    elif not uploaded_files and not input_text:
        st.warning("⚠️ Please upload resumes and enter a job description")
#========================================================================================================================================================================================
# ------------------------------------------------------------------------------------------------------------------------------------------------ 
elif st.session_state.user_type == "user_with_job_role":
    st.title("RezumeX - User (with Job Role)")
    st.subheader("Application Tracking System")

    if st.button("Back to Home"):
        set_user_type("welcome")

    # Job Role Selection
    st.markdown("<div class='job-role-selector'>", unsafe_allow_html=True)
    selected_job_role = st.selectbox("Select Job Role:", job_roles)
    st.markdown("</div>", unsafe_allow_html=True)

    input_text = st.text_area("Enter Job Description:", height=200)
    uploaded_file = st.file_uploader("Upload Your Resume (PDF)...", type=["pdf"])

    if uploaded_file and input_text:
        if st.button("Analyze Resume"):
            try:
                # Extract text directly from PDF (no image conversion)
                pdf_text = input_pdf_setup(uploaded_file)
                
                if not pdf_text:
                    st.error("Failed to extract text from PDF. Please ensure the file is valid.")
                    return

                with st.spinner("Analyzing resume..."):
                    # Prepare the analysis prompt
                    full_prompt = f"""
                    You are an experienced HR professional specializing in {selected_job_role}. 
                    Analyze this resume against the job description below:

                    Job Description:
                    {input_text}

                    Resume Text:
                    {pdf_text}

                    Provide detailed analysis covering:
                    1. ATS Score (Percentage Match) - Show as percentage and visual gauge
                    2. Missing Keywords (highlight in red)
                    3. Missing Skills (highlight in yellow) 
                    4. Resume Improvement Suggestions (bullet points)
                    5. Skill Development Recommendations
                    6. Relevant Course Links (as markdown links)
                    7. Overall Fit Assessment

                    Format the output with clear headings and visual elements.
                    """

                    # Get response from Gemini
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(full_prompt)
                    
                    # Display results
                    st.subheader("Resume Analysis Results")
                    st.markdown("---")
                    st.markdown(response.text)

                    # Optional: Extract and visualize ATS score
                    try:
                        ats_score = extract_ats_score(response.text)
                        if ats_score:
                            st.subheader("ATS Compatibility Score")
                            st.progress(ats_score/100)
                            st.caption(f"{ats_score}% match with job requirements")
                    except:
                        pass

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.exception(e)

    elif not input_text and uploaded_file:
        st.warning("Please enter a job description to analyze against.")
    elif not uploaded_file and input_text:
        st.warning("Please upload your resume PDF for analysis.")
    elif not uploaded_file and not input_text:
        st.warning("Please upload your resume and enter a job description.")
#===========================================================================================================================================
elif st.session_state.user_type == "linkedin" :
    st.title("LinkedIn Profile Analyzer")

    if st.button("Back to Home"):
        set_user_type("welcome") 

    job_description = st.text_area("Paste the Job Description:", height=200)

    linkedin_text = st.text_area("Paste your LinkedIn profile text:", height=300)

    target_skills_str = st.text_area("Enter target skills :", height=68)

    use_gemini = st.checkbox("Check The Box If You Want Profile Improving Suggestions As Well As Profile Analysis")

    if st.button("Analyze"):
        if not linkedin_text:
            st.warning("Please paste your LinkedIn profile text.")
        elif not target_skills_str:
            st.warning("Please enter at least one target skill.")
        elif not job_description:
            st.warning("Please paste the job description.")
        else:
            target_skills = [skill.strip() for skill in target_skills_str.split(",")]
            analysis_results = analyze_linkedin_text(linkedin_text, target_skills)

            st.subheader("Analysis Results:")
            st.write(f"**Skill Match Score:** {analysis_results['skill_match_score']:.2f}%")
            st.write(f"**Skills Found:** {', '.join(analysis_results['skills_found']) or 'None'}")
            st.write(f"**Years of Experience (approx.):** {analysis_results['experience_years']:.1f}")
            st.write(f"**Project Count:** {analysis_results['project_count']}")
            st.write(f"**Degrees:** {', '.join(analysis_results['degrees']) or 'None'}")

            st.subheader("Improving Suggestions...")

            if use_gemini:
                gemini_suggestions = generate_gemini_suggestions(linkedin_text, target_skills, job_description)
                if gemini_suggestions:
                    for suggestion in gemini_suggestions:
                        st.write(f"- {suggestion}")
                else:
                    st.write("Gemini could not generate suggestions.")
            else:
                # ... (Your existing rule-based suggestions)
                pass  # You can keep the old suggestions here if you want them as a fallback. 

elif st.session_state.user_type == "general_user":
    st.title("🎯 Career Path Explorer")
    st.subheader("Discover your best-fit roles based on your resume")
    
    if st.button("🏠 Back to Home"):
        set_user_state("welcome")
    
    with st.container():
        uploaded_file = st.file_uploader("📄 Upload Your Resume (PDF)", 
                                       type=["pdf"],
                                       help="We'll analyze your skills and suggest matching careers")
    
    if uploaded_file:
        with st.spinner("🔍 Analyzing your resume..."):
            try:
                # Extract text from PDF
                resume_text = input_pdf_setup(uploaded_file)
                
                if not resume_text:
                    st.error("❌ Could not extract text. Please upload a searchable PDF.")
                    st.info("💡 Tip: If your resume is scanned, try converting it to a text-based PDF first")
                    return
                
                # Extract skills
                skills = extract_skills_from(resume_text)
                
                if not skills:
                    st.warning("⚠️ No skills detected. Please check if your resume contains technical/professional skills")
                    return
                
                # Display results in tabs
                tab1, tab2, tab3, tab4 = st.tabs(["💼 Job Matches", "🚀 Skills", "📚 Learning", "💰 Salaries"])
                
                with tab1:
                    st.subheader("Your Best Career Matches")
                    job_roles = suggest_job_roles(skills)
                    
                    cols = st.columns(3)
                    for i, role in enumerate(job_roles[:9]):  # Show top 9
                        with cols[i%3]:
                            with st.container(border=True):
                                st.markdown(f"**{i+1}. {role}**")
                                st.progress(min((10-i)*10, 95))  # Visual ranking indicator
                
                with tab2:
                    st.subheader("Your Skills Analysis")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🛠️ Technical Skills")
                        tech_skills = [s for s in skills if s in [
                            "Python", "Java", "SQL", "Machine Learning", "AWS"]]
                        for skill in tech_skills:
                            st.markdown(f"- ✅ {skill}")
                    
                    with col2:
                        st.markdown("#### 🤝 Professional Skills")
                        soft_skills = [s for s in skills if s in [
                            "Communication", "Project Management", "Leadership"]]
                        for skill in soft_skills or ["None detected"]:
                            st.markdown(f"- ✨ {skill}")
                    
                    st.markdown("---")
                    st.subheader("🔥 Trending Technologies")
                    trending = suggest_trending_technologies()
                    st.write("Consider adding these to your skillset:")
                    for tech in trending:
                        st.markdown(f"- 🌟 {tech}")
                
                with tab3:
                    if job_roles:
                        primary_role = job_roles[0]
                        st.subheader(f"📖 Recommended Learning for {primary_role}")
                        
                        courses = suggest_online_courses(primary_role)
                        for course in courses[:5]:  # Limit to top 5
                            st.markdown(f"""
                            <div style="padding:10px;border-radius:5px;background:#f0f2f6;margin:5px">
                            🎓 **{course}**  
                            <small>[Find on Google](https://www.google.com/search?q={course.replace(' ','+')})</small>
                            </div>
                            """, unsafe_allow_html=True)
                
                with tab4:
                    if job_roles:
                        st.subheader("💵 Expected Salary Ranges")
                        
                        cols = st.columns(3)
                        for i, role in enumerate(job_roles[:3]):  # Top 3 roles
                            salary = suggest_salary_expectations(role)
                            with cols[i]:
                                with st.container(border=True):
                                    st.markdown(f"**{role}**")
                                    st.markdown(f"`{salary}`")
                                    st.markdown("*Median range*")
                
                # Success message
                st.balloons()
                st.success("🎉 Analysis complete! Explore the tabs above for personalized recommendations")
            
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.exception(e) if st.toggle("Show technical details") else None
# Cover Letter Generator Page
elif st.session_state.user_type == "cover_letter_generator":
    st.title("Cover Letter Generator")
    if st.button("Back to Home"):
        set_user_type("welcome") 
    # Initialize resume and job data
    resume_data = {}  
    job_data = {  
        "job_title": "",
        "company_name": "",
        "job_description": "",
        "key_requirements": ""
    }

    # Form for user input
    with st.form("cover_letter_form"):
        resume_data['name'] = st.text_input("Your Name", placeholder="Enter Your Name")
        resume_data['contact'] = {
            'email': st.text_input("Your Email", placeholder="Enter Your Email"), 
            'phone': st.text_input("Your Phone", placeholder="Enter Your Phone"), 
            'linkedin': st.text_input("Your LinkedIn Profile (Optional)", placeholder="Enter Your LinkedIn Profile")
        }
        resume_data['skills'] = st.text_area("Your Skills (comma-separated)", placeholder="Enter your skills, separated by commas")
        job_data["job_title"] = st.text_input("Job Title", placeholder="Enter Job Title")
        job_data["company_name"] = st.text_input("Company Name", placeholder="Enter Company Name")
        job_data["job_description"] = st.text_area("Job Description", placeholder="Enter Job Description", height=200)
        job_data["key_requirements"] = st.text_area("Key Requirements", placeholder="Enter Key Requirements", height=100)
        submitted = st.form_submit_button("Generate Cover Letter")

    # Generate cover letter on form submission
    if submitted:
        # Convert skills text to a list
        resume_data['skills'] = [skill.strip() for skill in resume_data['skills'].split(',')]

        # Generate cover letter using Gemini API
        cover_letter = generate_cover_letter(resume_data, job_data)
        st.subheader("Generated Cover Letter")
        st.write(cover_letter)

        # Option to download the cover letter
        st.download_button(
            label="Download Cover Letter",
            data=cover_letter,
            file_name="cover_letter.txt",
            mime="text/plain"
        )            
