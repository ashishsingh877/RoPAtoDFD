import json
import streamlit as st
import google.generativeai as genai


genai.configure(api_key=st.secrets["AIzaSyClulfLQjWuzdVWWMM3kdJOGhX_0zlb-8s"])


def generate_dfd(ropa):

    model = genai.GenerativeModel("gemini-pro")

    prompt = f"""
Convert the following RoPA data into DFD JSON structure.

Format:

{{
 "phases":[
   {{
    "name":"Process",
    "steps":[
      {{"id":"1","label":"Applicant","type":"external"}},
      {{"id":"2","label":"HR Team","type":"process"}}
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

    return json.loads(response.text)
