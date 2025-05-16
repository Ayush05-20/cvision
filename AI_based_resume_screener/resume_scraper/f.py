import os
import json
import logging
from typing import Dict, List, Optional


from resume_scraper.resume_processor import parse_resume_from_file
from resume_scraper.scraper import scrape_website, clean_body_content, split_dom_content
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM


logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    "description": "",
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
    "To improve the match, consider the following suggestions:
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
                print(f"\n🧾 Matching job: {job.get('job_title')}")
                match_result = self.llm.invoke(
                    matching_prompt.format(
                        resume_details=json.dumps(resume_data),
                        job_listing=json.dumps(job)
                    )
                )
                print("LLM raw output:")
                print(match_result)

                match_data = self._clean_json_response(match_result)
                matched_job = {**job, "match_details": match_data}
                matched_jobs.append(matched_job)
            except Exception as e:
                logger.error(f"Error matching resume to job: {e}")

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


def main():
    matcher = ResumeJobMatcher()

    
    user_location = input("Enter preferred job location: ").strip().lower()
    job_keyword = input("Enter job description or keyword: ").strip().lower()

    
    job_sites = [
        "https://www.linkedin.com/jobs/search/?currentJobId=" +"&keywords="+job_keyword.replace(" ", "%20") + "&location=" + user_location
    ]

    print("\n🔍 Scraping job listings...")
    job_listings = matcher.scrape_job_listings(job_sites)
    print(f"✅ Scraped {len(job_listings)} total jobs.")

    print("\n🧠 Filtering job listings...")
    filtered_jobs = matcher.filter_jobs(job_listings, location=user_location, keyword=job_keyword)
    print(f"✅ Found {len(filtered_jobs)} jobs after filtering by location & keyword.")

    if not filtered_jobs:
        print("⚠️ No jobs matched the filter. Saving empty result.")
        with open("output/top_5_matched_jobs.json", "w") as f:
            json.dump([], f, indent=2)
        return

    resume_file_path = "/Users/ayush/AI_based_resume_screener/__DATA__/Yug-Adhikari-FlowCV-Resume-20250324.pdf"
    with open(resume_file_path, "rb") as resume_file:
        matched_jobs = matcher.match_resume_to_jobs(resume_file, filtered_jobs)
        print(f"✅ Resume matched with {len(matched_jobs)} jobs.")

    if not matched_jobs:
        print("⚠️ LLM returned no valid matches. Using filtered jobs instead.")
        matched_jobs = filtered_jobs

    top_matches = matched_jobs[:5]

    os.makedirs("output", exist_ok=True)
    with open("output/top_5_matched_jobs.json", "w") as f:
        json.dump(top_matches, f, indent=2)

    print("💾 Top 5 job matches saved to output/top_5_matched_jobs.json")

if __name__ == "__main__":
    main()
