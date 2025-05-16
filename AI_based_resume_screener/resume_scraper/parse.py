import os
import json
import logging
from typing import Dict, List, Optional

# Import your existing modules
from resume_processor import prase_resume_from_file
from scraper import scrape_website, clean_body_content, split_dom_content
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResumeJobMatcher:
    def __init__(self, model_name="llama3.2"):
        """
        Initialize the Resume Job Matcher with an LLM model
        
        Args:
            model_name (str): Name of the Ollama model to use
        """
        self.llm = OllamaLLM(model=model_name)
        
    def scrape_job_listings(self, job_sites: List[str]) -> List[Dict]:
        """
        Scrape job listings from multiple websites
        
        Args:
            job_sites (List[str]): List of job website URLs to scrape
        
        Returns:
            List[Dict]: Parsed job listings
        """
        job_listings = []
        
        for site in job_sites:
            try:
                # Scrape the website
                html_content = scrape_website(site)
                
                if not html_content:
                    logger.warning(f"Failed to scrape content from {site}")
                    continue
                
                # Clean and split the content
                cleaned_content = clean_body_content(html_content)
                split_contents = split_dom_content(cleaned_content)
                
                # Parse job listings from the content
                for content in split_contents:
                    job_listing = self._extract_job_details(content)
                    if job_listing:
                        job_listings.append(job_listing)
            
            except Exception as e:
                logger.error(f"Error scraping {site}: {e}")
        
        return job_listings
    
    def _extract_job_details(self, content: str) -> Optional[Dict]:
        """
        Extract job details from scraped content
        
        Args:
            content (str): Scraped and cleaned job listing content
        
        Returns:
            Optional[Dict]: Extracted job details
        """
        # Create a prompt template for job detail extraction
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
            # Generate job details
            response = self.llm.invoke(
                job_extract_prompt.format(job_content=content)
            )
            
            # Clean and parse the JSON response
            job_details = self._clean_json_response(response)
            
            return job_details
        except Exception as e:
            logger.error(f"Error extracting job details: {e}")
            return None
    
    def _clean_json_response(self, response: str) -> Dict:
        """
        Clean and parse the JSON response from the LLM.

        Args:
            response (str): Raw LLM response

        Returns:
            Dict: Parsed and cleaned job details or an empty dict if parsing fails
        """
        import re

        # Remove markdown code block markers and strip whitespace
        response = response.replace("```json", "").replace("```", "").strip()

        # Try direct parsing first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract the JSON substring manually
            try:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]

                # Remove control characters that can break JSON
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error("Could not parse job details JSON")
                logger.error(f"Error: {e}")
                logger.error(f"Raw LLM Response: {response}")
                return {}

    
    def match_resume_to_jobs(self, resume_file, job_listings: List[Dict]) -> List[Dict]:
        """
        Match a resume to job listings
        
        Args:
            resume_file: File object of the resume
            job_listings (List[Dict]): List of job listings to match against
        
        Returns:
            List[Dict]: Matched job listings with match scores
        """
        # Parse the resume
        resume_data = prase_resume_from_file(resume_file)
        
        if 'error' in resume_data:
            logger.error("Failed to parse resume")
            return []
        
        # Create matching prompt
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
        "match_reasoning": ""
    }}

    Evaluation Criteria:
    - Compare skills, experience, and job requirements
    - Consider both technical and soft skills
    - Provide detailed reasoning for the match score
    - Location should be the person's current location
    - make it as user can write their location
 """
            )
        
        # Store matched jobs
        matched_jobs = []
        
        for job in job_listings:
            try:
                # Generate match score
                match_result = self.llm.invoke(
                    matching_prompt.format(
                        resume_details=json.dumps(resume_data),
                        job_listing=json.dumps(job)
                    )
                )
                
                # Clean and parse match result
                match_data = self._clean_json_response(match_result)
                
                # Combine job details with match information
                matched_job = {
                    **job,
                    "match_details": match_data
                }
                
                matched_jobs.append(matched_job)
            
            except Exception as e:
                logger.error(f"Error matching resume to job: {e}")
        
        # Sort matched jobs by match score in descending order
        matched_jobs.sort(key=lambda x: x.get('match_details', {}).get('match_score', 0), reverse=True)
        
        return matched_jobs

def main():
    # Example usage
    matcher = ResumeJobMatcher()
    
    # Job sites to scrape
    job_sites = [
        "https://www.linkedin.com/jobs/search/"
        # Add more job sites as needed
    ]
    
    # Scrape job listings
    job_listings = matcher.scrape_job_listings(job_sites)
    
    # Save scraped job listings
    os.makedirs("output", exist_ok=True)
    with open("output/job_listings.json", "w") as f:
        json.dump(job_listings, f, indent=2)
    
    # Load a sample resume file (replace with actual file path)         
    resume_file_path = "/Users/ayush/AI_based_resume_screener/__DATA__/Yug-Adhikari-FlowCV-Resume-20250324.pdf"    
    with open(resume_file_path, "rb") as resume_file:
        # Match resume to job listings
        matched_jobs = matcher.match_resume_to_jobs(resume_file, job_listings)
        
        # Save matched jobs
        with open("output/matched_jobs.json", "w") as f:
            json.dump(matched_jobs, f, indent=2)
    print("Job matching process completed.")

if __name__ == "__main__":
    main()