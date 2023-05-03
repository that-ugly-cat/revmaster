import pandas as pd
import streamlit as st
import base64
from st_aggrid import AgGrid, GridOptionsBuilder
import os
#import gitpush

# Initial configurations
####################################
st.set_page_config(page_title = 'RevMaster', page_icon = ':books:', layout = 'wide')

config_files = os.listdir('configs')
st.text(config_files)
if 'initial_config.py' not in config_files:
  st.header('No configuration found.')
  st.subheader('Let\'s set up a new project')
  with st.form("my_form"):
    project_title = st.text_input('Project title', '...')
    project_description = st.text_area('Text to analyze', '...')
    save_1 = st.form_submit_button("Save")
  if save_1:
    st.write(project_title, project_description)

else:
  st.text('...')
