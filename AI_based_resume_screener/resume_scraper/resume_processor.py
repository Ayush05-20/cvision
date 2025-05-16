# resume_processor.py
import os
from pypdf import PdfReader
import json
# Ensure resume_praser is in the same directory or accessible
from resume_scraper.resume_praser import ats_extractor # Import the ats_extractor function

# Assuming UPLOAD_PATH and save_file, extract_text_from_pdf are defined above this

UPLOAD_PATH = "__DATA__" # Ensure this is consistent
os.makedirs(UPLOAD_PATH, exist_ok=True)

def save_file(file_object, filename="file.pdf"):
    """Save uploaded file to disk"""
    # Use a more unique filename to avoid conflicts if processing multiple resumes
    # For example: filename = f"resume_{os.path.basename(file_object.name)}_{int(time.time())}.pdf"
    # But for simplicity, let's stick to the current logic based on your code
    file_path = os.path.join(UPLOAD_PATH, filename)
    # Add error handling for writing the file
    try:
        with open(file_path, "wb") as f:
            f.write(file_object.read())
        return file_path
    except Exception as e:
        print(f"Error saving file {filename}: {e}")
        return None


def extract_text_from_pdf(file_path):
    """Extracts all text from a PDF using pypdf"""
    if not file_path or not os.path.exists(file_path):
        print(f"Error: PDF file path is invalid or does not exist: {file_path}")
        return None
    try:
        reader = PdfReader(file_path)
        data = ""
        # Add check for encrypted files if necessary: if reader.is_encrypted: reader.decrypt("")
        for page in reader.pages:
            # Add error handling for page extraction
            try:
                data += page.extract_text() or "" # Use empty string if extract_text returns None
            except Exception as page_e:
                print(f"Warning: Could not extract text from a page: {page_e}")
                # Continue to the next page
        return data
    except Exception as e:
        print(f"Error extracting text from PDF {file_path}: {e}")
        return None

# FIX THIS FUNCTION
def parse_resume_from_file(file_object):

    # Save and read the file
    file_path = save_file(file_object)
    if not file_path:
        print("Failed to save resume file.")
        return {"error": "Failed to save file"} # Return an error dictionary

    resume_data = extract_text_from_pdf(file_path)
    # Optionally clean up the saved file after extraction
 


    if not resume_data:
        print("Failed to extract text from resume PDF.")
        return {"error": "Failed to extract text from PDF"} # Return an error dictionary

    prased_data = ats_extractor(resume_data) # Call your extractor

    if "error" in prased_data:
         print(f"Error reported by ats_extractor: {prased_data['error']}")
         # The ats_extractor already returns the error dict, just return it
         return prased_data
    else:
        # If no error from extractor, return the successfully parsed dictionary
        return prased_data

