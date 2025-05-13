import json
import os
import re

import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from glob import glob
import zipfile
import argparse
import flywheel
import logging

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Update the CSV file with the latest data from the Flywheel UNITY QA project.')
parser.add_argument('--apikey','-apikey',type=str,nargs='?',help='FW CLI API key')

args = parser.parse_args()
api_key = args.apikey

fw = flywheel.Client(api_key=api_key)
print(f"User: {fw.get_current_user().firstname} {fw.get_current_user().lastname}")

# for fw_project in fw.projects():
#     fw_project = fw_project.reload()
#     print(f"Project: {fw_project.label}")
    
#Given a list of phantom IDs, get the subject, and move it to UNITY-QA
#read the site_phantom_key.json file from utils
with open('utils/site_phantom_key.json') as f:
    site_phantom_key = json.load(f)

# Get the Phantom QA project
phantom_project = fw.lookup("unity/UNITY-QA")

group_names = ["global_map","prisma"]
project_ids = []
for group_name in group_names:    
    # Get the group
    group = fw.lookup(f"{group_name}")
    group = group.reload()
    
    # Get the projects in the group
    projects = group.projects()
    project_ids.extend([project.id for project in projects])

# group = fw.lookup(f"{group_name}")
# group = group.reload()
# projects = group.projects()
# project_ids = [project.id for project in projects]

#the values are the phantom IDS
#the keys are the site IDs
keys = list(site_phantom_key.values())
keys_renamed = ["137-"+key for key in keys]
keys_renamed.extend(["137"+key for key in keys])
keys_renamed.extend(["137_"+key for key in keys])

for key in keys_renamed:
    #phantom = fw.subjects.find_first(f"label={key}")

    phantoms = fw.subjects.find(f"label={key}")
    for phantom in phantoms:
        phantom = phantom.reload()
        
        if phantom is not None and phantom.project in project_ids:
            project = fw.projects.find_first(f"_id={phantom.project}")
            print(phantom.label)
            print(project.label)

            for session in phantom.sessions():
                print("session: ", session.label)
                # Add a tag to a session
                print("Adding tag to session: ", session.label)
                try:
                    session.add_tag('Phantom')
                except:
                    print("Error adding tag to session: ", session.label)
                    continue

                try:
                    phantom_subject = phantom_project.add_subject(label=phantom.label)    
                    print('Adding subject: ', phantom.label)                            
                except:
                    # If subject already exists, reload it
                    phantom_subject = phantom_project.subjects.find_one(f"label={phantom.label}")
                    print('Subject already exists: ', phantom.label)
                    
                # Move session to Phantom QA project
                dest_sub = phantom_subject.reload()
                try:
                    log.info("Moving session: ", session.label)
                    session.update({'subject': dest_sub.id})
                except Exception as e:
                    print("Error moving session; ",e)
                    continue




