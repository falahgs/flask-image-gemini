# Efficient Structured Data Extraction from Shared Screens and Images Using Flask and Google Gemini AI

This web application allows users to upload images or share their screen for data extraction. The app uses **Google Gemini AI** to analyze images and extract structured data, such as personal information, document details, and other relevant fields. The extracted data can then be downloaded in either **JSON** or **Excel** format.

## Features
- **Screen Capture**: Users can capture screenshots (via the browser) for analysis.
- **Image Upload**: Users can upload images (such as documents, receipts, etc.) for data extraction.
- **Data Extraction**: The app uses **Google Gemini AI** to extract structured data from the images.
- **Downloadable Results**: Extracted data can be downloaded in **JSON** or **Excel** format.

## Prerequisites

Before running the app, ensure that you have the following installed:
- Python 3.x
- Flask
- Google Gemini API Key (for AI-based extraction)
- Required Python libraries: `Flask`, `google-generativeai`, `Pillow`, `pandas`, `openpyxl`, `pydantic`

### Install Required Libraries

Use pip to install the necessary dependencies:

```bash
pip install Flask google-generativeai pydantic Pillow pandas openpyxl
