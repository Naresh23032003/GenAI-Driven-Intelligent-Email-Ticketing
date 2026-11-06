# GenAI-Driven Intelligent Email Ticketing

[![CI](https://github.com/Naresh23032003/GenAI-Driven-Intelligent-Email-Ticketing/actions/workflows/ci.yml/badge.svg)](https://github.com/Naresh23032003/GenAI-Driven-Intelligent-Email-Ticketing/actions/workflows/ci.yml)

This repository contains the source code for an intelligent email processing system that automates complaint classification and triage. Designed for service-oriented industries such as logistics and customer support, the system leverages Natural Language Processing (NLP) techniques, a lightweight architecture, and integration with Ollama's LLAMA 3 model to enhance operational efficiency.

## Live Demo
[![Watch the Demo](https://img.youtube.com/vi/66db5RdDg58/0.jpg)](https://www.youtube.com/watch?v=66db5RdDg58)

Click the image above to watch the full demonstration on YouTube.

---

## Key Features

- Automated Email Parsing: Extract sender, subject, body, and timestamp.
- Sentiment Analysis: Identify negative emails using rule-based detection and LLAMA 3-powered analysis.
- Complaint Classification: Map issues to a predefined issue dictionary.
- Team Assignment: Route tickets to the correct operational team.
- Dashboard: View tickets by team, date, and sentiment.
- Lightweight Backend: Local database for quick and easy deployment.
- Integration with Ollama's LLAMA 3 for advanced text understanding and contextual analysis.

---

## System Architecture
![System Architecture](architecture.png)

---

## Repository Structure
```
📦 GenAI-Driven-Intelligent-Email-Ticketing
├── app.py              # Dashboard for ticket view & team analytics
├── db.py               # Backend for storing ticket metadata
├── email_processor.py  # Core logic: parsing, sentiment, and classification
├── sample_data/        # Sample dataset with 500 emails
├── demo_video.mp4      # Video demonstration of the system (20 MB)
├── requirements.txt    # Python dependencies
└── README.md           # This documentation file
```

---

## Setup Instructions

### Clone the Repository
```bash
git clone https://github.com/Naresh23032003/GenAI-Driven-Intelligent-Email-Ticketing.git
cd Naresh23032003/GenAI-Driven-Intelligent-Email-Ticketing
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run the App
```bash
streamlit run app.py
```

The dashboard will open in your default browser at `http://localhost:8501`.

---

## How It Works

1. **Input**: Incoming emails are parsed to extract content and metadata.
2. **Processing**: Sentiment is detected and categorized using keyword rules and LLAMA 3-based models.
3. **Classification**: Negative sentiment emails are mapped to pre-defined issue labels.
4. **Routing**: Each issue is linked to a responsible team (e.g., Logistics, Payment, Support).
5. **Display**: A real-time dashboard displays complaints, statuses, and analytics.

---

## Sample Data
The `sample_data/` folder contains a dataset of 500 sample emails used to demonstrate system functionality. Use this data to test the system or as a reference format for integrating additional datasets.

---

## Ollama - LLAMA 3 Integration
This system integrates with [Ollama](https://ollama.com/) to utilize LLAMA 3 models for advanced text analysis and sentiment understanding. To use LLAMA 3 in the project:

```python
import ollama
response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': 'Summarize this email: ...'}])
print(response['message']['content'])
```

Ensure that Ollama is running locally and the LLAMA 3 model is downloaded and ready.

---

## License
This project is licensed under the MIT License.

---

## Acknowledgements
Built as part of a research project for ICACECS 2025, this system integrates simple yet effective tools and advanced models to deliver measurable improvements in service efficiency.

---

## Authors
- Primary Developers & Researchers: Naresh R, Sreeja Sunkeswaram

For questions or collaboration requests, please open an issue or contact us.
