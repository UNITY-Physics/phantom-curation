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


def acquisitions_have_files(session):
    complete = True
    for acq in session.acquisitions():
        acq = acq.reload()
        print(acq.label, " has ", len(acq.files), " files.")
        complete = complete and (len(acq.files) > 0)
        
    return complete



def main(fw):

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

        phantoms = fw.subjects.find(f"label={key}") #look for the Phantom subject in all global_map and prisma projects
        for phantom in phantoms:
            phantom = phantom.reload()
            
            if phantom is not None and phantom.project in project_ids: #filtering prisma and global_map projects
                project = fw.projects.find_first(f"_id={phantom.project}")
                print("project: ", project.label, " phantom: ", phantom.label)

                try:
                    phantom_subject = phantom_project.add_subject(label=phantom.label)    
                    print('Adding subject: ', phantom.label)                            
                except Exception as e:
                    # If subject already exists, reload it
                    phantom_subject = phantom_project.subjects.find_one(f"label={phantom.label}")
                    print('Subject already exists: ', phantom.label )
                        
                    # Move session to Phantom QA project
                    dest_sub = phantom_subject.reload()
                
                for session in phantom.sessions():
                    # Add a tag to a session
                    print("Adding tag to session: ", session.label)
                    try:
                        session.add_tag('Phantom')
                    except Exception as e:
                        print("Error adding tag to session: ", session.label, e)
                        #session.update({'subject': phantom_subject.id})

                    existing_session = dest_sub.sessions.find_first(f"label={session.label}")
                    
                    if existing_session:
                        if acquisitions_have_files(existing_session):
                            print(f"✅ Session '{session.label}' exists and is complete — skipping.")
                            continue
                        else:
                            print(f"🗑️ Session '{session.label}' is incomplete — deleting from phantom_QA.")
                            try:
                                # Delete the existing session if it exists and is incomplete
                                fw.delete_session(existing_session.id)
                                # existing_session.delete()
                                print(f"✔️ Deleted session '{session.label}' from phantom_QA.")
                            except Exception as e:
                                print(f"❌ Failed to delete session '{session.label}': {e}")
                                continue  # Skip reassign if we can't delete

                    # Reassign session to phantom_QA subject
                    try:
                        print(f"🔄 Moving session '{session.label}' to phantom_QA...")
                        session.update({'subject': dest_sub.id})
                    except Exception as e:
                        print(f"❌ Failed to reassign session '{session.label}': {e}")

                    




if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Update the CSV file with the latest data from the Flywheel UNITY QA project.')
    parser.add_argument('--apikey','-apikey',type=str,nargs='?',help='FW CLI API key')

    args = parser.parse_args()
    api_key = args.apikey

    fw = flywheel.Client(api_key=api_key)
    print(f"User: {fw.get_current_user().firstname} {fw.get_current_user().lastname}")
    main(fw)