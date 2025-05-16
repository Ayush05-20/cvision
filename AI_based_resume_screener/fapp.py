import os
import json
import logging
from typing import Dict, List, Optional
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from resume_scraper.resume_processor import parse_resume_from_file
from resume_scraper.scraper import scrape_website, clean_body_content, split_dom_content
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='frontend')
app.secret_key = os.urandom(24).hex()  # Secure random secret key
app.config['UPLOAD_FOLDER'] = 'upload'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'doc', 'rtf'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('output', exist_ok=True)

class ResumeJobMatcher:
    def __init__(self, model_name="llama3.2"):
        self.llm = OllamaLLM(model=model_name)
        
    def scrape_job_listings(self, job_sites: List[str]) -> List[Dict]:
        job_listings = []
        for site in job_sites:
            try:
                html_content = scrape_website(site)
                if not html_content:
                    logger.warning(f"Failed to scrape content from {site}")
                    continue
                cleaned_content = clean_body_content(html_content)
                split_contents = split_dom_content(cleaned_content)
                for content in split_contents:
                    job_listing = self._extract_job_details(content)
                    if job_listing:
                        job_listings.append(job_listing)
            except Exception as e:
                logger.error(f"Error scraping {site}: {e}")
        return job_listings
    
    def _extract_job_details(self, content: str) -> Optional[Dict]:
        job_extract_prompt = PromptTemplate(
            input_variables=["job_content"],
            template="""Extract structured job details from the following job listing content:

Content: {job_content}

Please provide a JSON response with the following structure:
{{
    "job_title": "",
    "company": "",
    "location": "",
    "requirements": [],
    "skills_required": [],
    "experience_level": "",
    "salary_range": ""
}}

Ensure the response is a valid JSON object. If information is not found, use empty strings or empty lists."""
        )
        try:
            response = self.llm.invoke(job_extract_prompt.format(job_content=content))
            return self._clean_json_response(response)
        except Exception as e:
            logger.error(f"Error extracting job details: {e}")
            return None

    def _clean_json_response(self, response: str) -> Dict:
        import re
        response = response.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error("Could not parse job details JSON")
                logger.error(f"Error: {e}")
                logger.error(f"Raw LLM Response: {response}")
                return {}

    def match_resume_to_jobs(self, resume_file, job_listings: List[Dict]) -> List[Dict]:
        resume_data = parse_resume_from_file(resume_file)
        if 'error' in resume_data:
            logger.error("Failed to parse resume")
            return []
        
        matching_prompt = PromptTemplate(
            input_variables=["resume_details", "job_listing"],
            template="""Compare the following resume details with a job listing and provide a match score and reasoning:

Resume Details:
{resume_details}

Job Listing:
{job_listing}

Please provide a JSON response with:
{{
    "match_score": 0-100,
    "matched_skills": [],
    "missing_skills": [],
    "match_reasoning": "",
    "matched_experience": [],
    "improvement_suggestions": [],
    "additional_comments": "Provide any additional comments or insights about the match."
}}

Evaluation Criteria:
- Compare skills, experience, and job requirements
- Consider both technical and soft skills
- Provide detailed reasoning for the match score
- Give a score of 0-100 based on the match
- Provide a list of matched and missing skills
- Provide a detailed reasoning for the match score
- Ensure the response is a valid JSON object.
- Make sure to include all relevant details from the resume and job listing.
"""
        )

        matched_jobs = []
        for job in job_listings:
            try:
                logger.info(f"🧾 Matching job: {job.get('job_title', 'Unknown Title')}")
                match_result = self.llm.invoke(
                    matching_prompt.format(
                        resume_details=json.dumps(resume_data),
                        job_listing=json.dumps(job)
                    )
                )
                logger.debug(f"LLM raw output: {match_result}")

                match_data = self._clean_json_response(match_result)
                matched_job = {**job, "match_details": match_data or {
                    "match_score": 0,
                    "matched_skills": [],
                    "missing_skills": [],
                    "match_reasoning": "No match data available.",
                    "matched_experience": [],
                    "improvement_suggestions": [],
                    "additional_comments": ""
                }}
                matched_jobs.append(matched_job)
            except Exception as e:
                logger.error(f"Error matching resume to job: {e}")
                matched_jobs.append({
                    **job,
                    "match_details": {
                        "match_score": 0,
                        "matched_skills": [],
                        "missing_skills": [],
                        "match_reasoning": "Error during matching.",
                        "matched_experience": [],
                        "improvement_suggestions": [],
                        "additional_comments": str(e)
                    }
                })

        matched_jobs.sort(
            key=lambda x: x.get("match_details", {}).get("match_score", 0),
            reverse=True
        )
        return matched_jobs

    def filter_jobs(self, job_listings, location="", keyword=""):
        filtered = []
        location = location.lower()
        keyword = keyword.lower()

        for job in job_listings:
            job_location = str(job.get("location", "")).lower()
            job_title = str(job.get("job_title", "")).lower()
            job_description = str(job.get("description", "")).lower()

            location_match = location in job_location or not location
            keyword_match = (
                keyword in job_title or 
                keyword in job_description or 
                any(keyword in req.lower() for req in job.get("requirements", []))
            )

            if location_match and keyword_match:
                filtered.append(job)

        return filtered[:5]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Validate file upload
        if 'resume' not in request.files:
            flash('No file part in the request', 'error')
            return redirect(url_for('upload'))
        
        file = request.files['resume']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('upload'))
        
        if not allowed_file(file.filename):
            flash('File type not allowed. Please upload PDF, DOCX, DOC, or RTF.', 'error')
            return redirect(url_for('upload'))

        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.debug(f"File saved to: {filepath}")

        # Get form data
        location = request.form.get('location', '').strip().lower()
        job_preference = request.form.get('job-preference', '').strip().lower()

        try:
            # Process resume and get matches
            matcher = ResumeJobMatcher()
            job_sites = [
                f"https://www.linkedin.com/jobs/search/?keywords={job_preference.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
            ]
            logger.info("🔍 Scraping job listings...")
            job_listings = matcher.scrape_job_listings(job_sites)
            logger.info(f"✅ Scraped {len(job_listings)} total jobs.")

            logger.info("🧠 Filtering job listings...")
            filtered_jobs = matcher.filter_jobs(job_listings, location=location, keyword=job_preference)
            logger.info(f"✅ Found {len(filtered_jobs)} jobs after filtering by location & keyword.")

            if not filtered_jobs:
                logger.warning("⚠️ No jobs matched the filter. Saving empty result.")
                flash('No jobs matched your criteria.', 'error')
                os.remove(filepath)
                return redirect(url_for('upload'))

            with open(filepath, 'rb') as resume_file:
                logger.info("Matching resume to jobs...")
                matched_jobs = matcher.match_resume_to_jobs(resume_file, filtered_jobs)
                logger.info(f"✅ Resume matched with {len(matched_jobs)} jobs.")

            os.remove(filepath)  # Clean up uploaded file

            if not matched_jobs:
                logger.warning("⚠️ LLM returned no valid matches. Using filtered jobs instead.")
                matched_jobs = filtered_jobs

            # Save top matches
            top_matches = matched_jobs[:5]
            with open('output/top_5_matched_jobs.json', 'w') as f:
                json.dump(top_matches, f, indent=2)
            logger.info("💾 Top 5 job matches saved to output/top_5_matched_jobs.json")

            flash('Resume uploaded and processed successfully!', 'success')
            return redirect(url_for('results'))

        except Exception as e:
            logger.error(f"Error processing resume: {e}")
            flash(f'Error processing resume: {str(e)}', 'error')
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(url_for('upload'))

    return render_template('upload.html')

@app.route('/results')
def results():
    try:
        with open('output/top_5_matched_jobs.json', 'r') as f:
            job_matches = json.load(f)
        logger.info(f"Job matches data: {json.dumps(job_matches, indent=2)}")
        return render_template('results.html', job_matches=job_matches)
    except FileNotFoundError:
        flash('No job matches found. Please upload your resume first.', 'error')
        return redirect(url_for('upload'))
    except Exception as e:
        logger.error(f"Error loading results: {e}")
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('upload'))

@app.route('/login-signup')
def login_signup():
    return render_template('login-signup.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('howitworks.html')

@app.route('/about-us')
def about_us():
    return render_template('about-us.html')

if __name__ == '__main__':
    app.run(debug=True)