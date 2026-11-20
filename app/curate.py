import json
import os
import re


from tqdm import tqdm
from datetime import datetime
from glob import glob
import zipfile
import argparse
import flywheel
import logging
from helpers import acquisitions_have_files, has_complete_ghost_analysis_with_files, clean_session_analyses


log = logging.getLogger(__name__)




def main(fw):

    #Given a list of phantom IDs, get the subject, and move it to UNITY-QA
    #read the site_phantom_key.json file from utils
    with open('utils/site_phantom_key.json') as f:
        site_phantom_key = json.load(f)

    # Get the Phantom QA project
    phantom_project = fw.lookup("unity/UNITY-QA")
    gear_ghost =  fw.lookup('gears/ghost')

    group_names = ["global_map","prisma","rise"]
    project_ids = []
    for group_name in group_names:    
        # Get the group
        group = fw.lookup(f"{group_name}")
        group = group.reload()
        
        # Get the projects in the group
        projects = group.projects()
        project_ids.extend([project.id for project in projects])

    #the values are the phantom IDS
    #the keys are the site IDs
    keys = list(site_phantom_key.values())
    keys_renamed = ["137-"+key for key in keys]
    keys_renamed.extend(["137"+key for key in keys])
    keys_renamed.extend(["137_"+key for key in keys])

    for key in keys_renamed:
        phantoms = fw.subjects.find(f"label={key}") #look for the Phantom subject in all global_map and prisma projects
        for phantom in phantoms:
            phantom = phantom.reload()
            
            if phantom is not None and phantom.project in project_ids: #filtering prisma and global_map projects
                project = fw.projects.find_first(f"_id={phantom.project}")
                print("project: ", project.label, " phantom: ", phantom.label)
                
                try:
                    phantom_subject = phantom_project.add_subject(label=phantom.label)  
                    dest_sub = phantom_subject.reload()  
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
                            print(f"🗑️ Session '{session.label}' is incomplete — deleting from UNITY_QA.")
                            try:
                                # Delete the existing session if it exists and is incomplete
                                fw.delete_session(existing_session.id)
                                # existing_session.delete()
                                print(f"✔️ Deleted session '{session.label}' from UNITY_QA.")
                            except Exception as e:
                                print(f"❌ Failed to delete session '{session.label}': {e}")
                                continue  # Skip reassign if we can't delete

                    # Reassign session to UNITY_QA subject
                    try:
                        print(f"🔄 Moving session '{session.label}' to UNITY_QA...")
                        clean_session_analyses(session, fw)
                        session.update({'subject': dest_sub.id})
                        session = session.reload()
                        #Submit ghost job if the session has acquisitions with files and no complete ghost analysis
                        if acquisitions_have_files(session) and not has_complete_ghost_analysis_with_files(session):
                            print(f"📤 Submitting ghost job for session '{session.label}'...")
                            dest = session
                            time_fmt = "%Y%m%d_%H%M%S"
                            # Clear session analyses if any and schedule ghost analysis with helper functions
                            analysis_label = f'ghost_{datetime.now().strftime(time_fmt)}'
                            print("This session does not have a complete ghost job",  {session.label})
                            job_id = gear_ghost.run(
                                analysis_label=analysis_label,
                                destination=dest,
                                tags=["qa", "ghost", "gpu","auto"],
                                config={}
                            )
                            
                
                        else:
                            print(f"⚠️ Session '{session.label}' does not meet criteria for ghost job submission.")
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
