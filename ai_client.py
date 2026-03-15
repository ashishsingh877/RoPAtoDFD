import json
import streamlit as st
import google.generativeai as genai


# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


def generate_dfd(ropa):

    try:

        model = genai.GenerativeModel("gemini-pro")

        prompt = f"""
Return ONLY valid JSON.

Convert this RoPA data into DFD JSON.

Format:

{{
 "phases":[
   {{
     "name":"Process",
     "steps":[
       {{"id":"1","label":"User","type":"external"}},
       {{"id":"2","label":"System","type":"process"}}
     ],
     "flows":[
       {{"from":"1","to":"2"}}
     ]
   }}
 ]
}}

RoPA:
{ropa}
"""

        response = model.generate_content(prompt)

        text = response.text.strip()

        text = text.replace("```json", "").replace("```", "")

        return json.loads(text)

    except Exception:

        # fallback if Gemini fails
        return {
            "phases":[
                {
                    "name":"RoPA Flow",
                    "steps":[
                        {"id":"1","label":"Data Subject","type":"external"},
                        {"id":"2","label":"Organization System","type":"process"}
                    ],
                    "flows":[
                        {"from":"1","to":"2"}
                    ]
                }
            ]
        }
