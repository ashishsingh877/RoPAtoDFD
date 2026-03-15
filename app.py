import streamlit as st
import json
from ropa_parser import parse_ropa
from ai_client import generate_dfd
from drawio_export import generate_drawio_xml


st.title("RoPA → Professional DFD Generator")


uploaded = st.file_uploader("Upload RoPA Excel", type=["xlsx"])


if uploaded:

    ropa_data = parse_ropa(uploaded)

    st.success("RoPA Parsed Successfully")

    if st.button("Generate DFD"):

        with st.spinner("AI generating DFD structure..."):

            dfd_json = generate_dfd(ropa_data)

        st.success("DFD Structure Created")

        st.json(dfd_json)

        xml = generate_drawio_xml(dfd_json)

        st.download_button(
            "Download Professional Draw.io DFD",
            xml,
            file_name="dfd.drawio",
            mime="application/xml"
        )
