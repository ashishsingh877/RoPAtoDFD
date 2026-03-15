import json
import streamlit as st
import google.generativeai as genai


# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


def generate_dfd(ropa):

    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
You are a system architect.

Convert the following RoPA information into a structured DFD JSON.

STRICT RULES:
- Only return JSON
- No explanations
- Valid JSON only

Format:

{{
 "phases":[
   {{
    "name":"Recruitment",
    "steps":[
      {{"id":"1","label":"Job Applicant","type":"external"}},
      {{"id":"2","label":"HR Team","type":"process"}}
    ],
    "flows":[
      {{"from":"1","to":"2"}}
    ]
   }}
 ]
}}

RoPA Data:
{ropa}
"""

    response = model.generate_content(prompt)

    text = response.text.strip()

    # remove markdown if Gemini adds it
    text = text.replace("```json", "").replace("```", "")

    try:
        return json.loads(text)

    except Exception:
        # fallback if AI response breaks
        return {
            "phases":[
                {
                    "name":"RoPA Process",
                    "steps":[
                        {"id":"1","label":"Data Subject","type":"external"},
                        {"id":"2","label":"Processing System","type":"process"}
                    ],
                    "flows":[
                        {"from":"1","to":"2"}
                    ]
                }
            ]
        }
