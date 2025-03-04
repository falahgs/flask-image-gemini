from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import os
from dotenv import load_dotenv
from PIL import Image
import base64
import io
import json
import pandas as pd
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

load_dotenv()

app = Flask(__name__)

# Configure Google Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Define data schemas
class AddressInfo(BaseModel):
    street: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State/Province")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")

class PersonInfo(BaseModel):
    full_name: Optional[str] = Field(None, description="Full name of person")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[AddressInfo] = Field(None, description="Address information")

class DocumentInfo(BaseModel):
    document_type: Optional[str] = Field(None, description="Type of document")
    document_date: Optional[str] = Field(None, description="Date on document")
    document_id: Optional[str] = Field(None, description="Document identifier")

class ExtractedData(BaseModel):
    person_info: Optional[PersonInfo] = Field(None, description="Personal information")
    document_info: Optional[DocumentInfo] = Field(None, description="Document information")
    additional_fields: Dict[str, Any] = Field(default_factory=dict, description="Any additional extracted fields")

def format_filename(prefix):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    return f"{prefix}_{timestamp}"

def extract_structured_data(image):
    # Create a detailed prompt for structured data extraction
    prompt = """
    Analyze this image and extract all text into a structured dataset format. Follow these guidelines:

    1. Identify and categorize information into these main sections:
       - Personal Information (name, contact details, address)
       - Document Information (type, date, ID numbers)
       - Additional Fields (any other relevant information)

    2. For each field, extract:
       - Field value
       - Data type (text, number, date)
       - Confidence level (high, medium, low)

    3. Organize related fields into logical groups:
       - Address fields together
       - Contact information together
       - Document-specific information together

    4. Expected structure:
       {
         "person_info": {
           "full_name": "John Doe",
           "email": "email@example.com",
           "phone": "123-456-7890",
           "address": {
             "street": "123 Main St",
             "city": "Anytown",
             "state": "ST",
             "postal_code": "12345"
           }
         },
         "document_info": {
           "document_type": "Invoice",
           "document_date": "2024-03-20",
           "document_id": "INV-12345"
         },
         "additional_fields": {
           "field_name": "value"
         }
       }

    Important: Extract all text precisely as shown in the image and maintain the hierarchical structure.
    """
    
    response = model.generate_content([prompt, image])
    
    # Parse the response into our schema
    try:
        # Clean up the response text by removing markdown code blocks
        response_text = response.text.strip()
        if response_text.startswith('```'):
            # Remove the first line (```json) and last line (```)
            response_text = '\n'.join(response_text.split('\n')[1:-1])
        
        # Parse the JSON string into a dictionary
        data_dict = json.loads(response_text)
        extracted_data = ExtractedData(**data_dict)
        return extracted_data.model_dump()
    except Exception as e:
        return {"error": f"Failed to parse response: {str(e)}", "raw_text": response.text}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_screen():
    try:
        # Get the image data from the request
        image_data = request.json['image']
        # Remove the data URL prefix
        image_data = image_data.split(',')[1]
        
        # Convert base64 to image
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Extract structured data from the image
        extracted_text = extract_structured_data(image)
        
        # Since extracted_text is already a dictionary, we don't need to parse it
        result = json.dumps(extracted_text, indent=2)
        
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-json', methods=['POST'])
def download_json():
    try:
        data = request.json['data']
        # Ensure data is properly serialized
        if isinstance(data, dict):
            json_bytes = json.dumps(data, indent=2).encode('utf-8')
        else:
            # If it's a string, try to parse it first to validate JSON
            try:
                parsed_data = json.loads(data)
                json_bytes = json.dumps(parsed_data, indent=2).encode('utf-8')
            except json.JSONDecodeError:
                # If parsing fails, wrap the raw string in a structure
                fallback_data = {
                    "rawText": data,
                    "extractionTime": datetime.now().isoformat(),
                    "status": "unstructured"
                }
                json_bytes = json.dumps(fallback_data, indent=2).encode('utf-8')
        
        # Create in-memory file
        mem_file = io.BytesIO(json_bytes)
        mem_file.seek(0)
        
        filename = format_filename("analysis_result") + ".json"
        
        return send_file(
            mem_file,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-excel', methods=['POST'])
def download_excel():
    try:
        data = request.json['data']
        # Ensure data is properly parsed
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError:
                parsed_data = {
                    "additional_fields": {"raw_text": data},
                    "person_info": {},
                    "document_info": {}
                }
        else:
            parsed_data = data

        # Function to convert list of dicts to DataFrame
        def process_data(data_list):
            if isinstance(data_list, list):
                return pd.DataFrame(data_list)
            elif isinstance(data_list, dict):
                return pd.DataFrame([data_list])
            else:
                return pd.DataFrame()

        # Process each section of data
        person_info = parsed_data.get('person_info', {})
        document_info = parsed_data.get('document_info', {})
        additional_fields = parsed_data.get('additional_fields', {})

        # Create DataFrames for each section
        person_df = process_data(person_info)
        document_df = process_data(document_info)
        
        # Handle additional fields that might contain lists
        additional_dfs = {}
        for key, value in additional_fields.items():
            if isinstance(value, list):
                # If it's a list of dictionaries, create a separate DataFrame
                df = process_data(value)
                if not df.empty:
                    additional_dfs[key] = df
            else:
                # For single values, create a simple one-row DataFrame
                additional_dfs['misc'] = pd.DataFrame([additional_fields])

        # Create Excel file in memory
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Write each section to a different worksheet
            if not person_df.empty:
                person_df.to_excel(writer, sheet_name='Personal Info', index=False)
            
            if not document_df.empty:
                document_df.to_excel(writer, sheet_name='Document Info', index=False)
            
            # Write additional fields to separate sheets
            for sheet_name, df in additional_dfs.items():
                # Clean sheet name (Excel has a 31 character limit for sheet names)
                clean_sheet_name = str(sheet_name)[:31]
                df.to_excel(writer, sheet_name=clean_sheet_name, index=False)
            
            # Auto-adjust columns for each worksheet
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(worksheet.columns):
                    max_length = 0
                    column = col[0].column_letter  # Get the column letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column].width = min(adjusted_width, 50)

        excel_buffer.seek(0)
        filename = format_filename("structured_data") + ".xlsx"
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
