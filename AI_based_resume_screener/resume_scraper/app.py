import streamlit as st
import os
import json
from resume_scraper.f import ResumeJobMatcher 


matcher = ResumeJobMatcher()


st.title("🧠 AI Resume Job Matcher")


st.sidebar.header("Enter Search Criteria")
location = st.sidebar.text_input("Preferred Location", value="Kathmandu")
keyword = st.sidebar.text_input("Job Keyword", value="Software Engineer")


st.subheader("Upload Your Resume")
uploaded_file = st.file_uploader("Choose a PDF or DOCX resume", type=["pdf", "docx"])

if uploaded_file and location and keyword:
    with st.spinner("🔍 Scraping job listings and processing your resume..."):
        
        job_sites = [
            f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '%20')}&location={location}"
        ]
        job_listings = matcher.scrape_job_listings(job_sites)
        filtered_jobs = matcher.filter_jobs(job_listings, location=location, keyword=keyword)

        if not filtered_jobs:
            st.warning("⚠️ No jobs matched your filters.")
        else:
            matched_jobs = matcher.match_resume_to_jobs(uploaded_file, filtered_jobs)
            top_matches = matched_jobs[:5]

            st.success(f"✅ Top {len(top_matches)} job matches found!")

            for i, job in enumerate(top_matches, 1):
                match_details = job.get("match_details", {})
                st.markdown(f"### {i}. {job.get('job_title', 'Unknown Job')}")
                st.write(f"**Company:** {job.get('company')}")
                st.write(f"**Location:** {job.get('location')}")
                st.write(f"**Score:** {match_details.get('match_score', 'N/A')}/100")
                st.write(f"**Matched Skills:** {', '.join(match_details.get('matched_skills', []))}")
                st.write(f"**Missing Skills:** {', '.join(match_details.get('missing_skills', []))}")
                st.write(f"**Reasoning:** {match_details.get('match_reasoning', '')}")
                st.write("---")

    
    if st.button("💾 Download Match Report as JSON"):
        os.makedirs("output", exist_ok=True)
        json_path = "output/top_5_matched_jobs.json"
        with open(json_path, "w") as f:
            json.dump(top_matches, f, indent=2)
        with open(json_path, "rb") as f:
            st.download_button("Download JSON", f, file_name="top_5_matched_jobs.json")

else:
    st.info("📄 Please upload a resume and provide location + keyword to proceed.")
