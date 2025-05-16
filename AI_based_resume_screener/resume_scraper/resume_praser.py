# resume_praser.py
import google.generativeai as genai
import os
import json
import re
from pypdf import PdfReader
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API key is not found. Please set the GEMINI_API_KEY environment variable.")
    
genai.configure(api_key=api_key)

def clean_json_response(text):
    """
    Cleans the AI response to extract valid JSON content.
    """
 
    text = text.replace("```json", "").replace("```", "")
    

    try:
        start = text.index('{')
        end = text.rindex('}') + 1
        json_str = text[start:end]
        
        
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
        
        return json_str
    except ValueError:
        return text  

def ats_extractor(resume_data):
    """
    Extracts ATS-friendly information from the resume data.
    
    Args:
        resume_data (str): The resume data in string format.
        
    Returns:
        dict: A dictionary containing extracted information.
    """
    

    prompt = """
   You are an ATS (Applicant Tracking System) that reads resumes and extracts relevant information.
    From the given resume data, extract the following information and return it in valid JSON format:
    {
        "Full Name": "",
        "Email Address": "",
        "Phone Number": "",
        "LinkedIn Profile URL": "",
        "Education": [],
        "Work Experience": [
            {
                "Company": "",
                "Position": "",
                "Duration": "",
                "Description": ""
            }
        ],
        "Technical Skills": [],
        "Soft Skills": [],
        "Certifications": [],
        "Projects": [
            {
                "Name": "",
                "Description": "",
                "Technologies": [],
                "URL": ""
            }
        ]
    }
    
    IMPORTANT:
    1. Return ONLY valid JSON format (no surrounding text or markdown)
    2. Education should be an array of strings
    3. Work Experience should include company, position, duration, and brief description
    4. Projects should include name, description, technologies used, and URL (if available)
    5. Keep descriptions concise but informative
    6. If information is missing, use empty arrays or empty strings
    7. Ensure all special characters are properly escaped
    8. Pay special attention to extracting all projects mentioned in the resume
    9. For projects, focus on identifying personal projects, academic projects, open-source contributions, etc.
    """
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    try:
        response = model.generate_content([
            {"role": "user", 
             "parts": [f"{prompt} \n\n Resume Text:\n {resume_data}"]}
        ])
        
   
        cleaned_response = clean_json_response(response.text)
        parsed_data = json.loads(cleaned_response)
        
        return parsed_data
        
    except Exception as e:
        print(f"Error in AI processing: {e}")
        return {
            "error": str(e),
            "raw_response": response.text if 'response' in locals() else None
        }

# def extract_text_from_pdf(file_path):
#     """Extracts all text from a PDF using pypdf"""
#     try:
#         reader = PdfReader(file_path)
#         data = "" 
#         for page in reader.pages:
#             data += page.extract_text()  
#         return data
#     except Exception as e:
#         print(f"Error extracting text from PDF: {e}")
#         return None