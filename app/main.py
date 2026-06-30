"""Main module."""
import flywheel
import logging
import os
import json
from datetime import datetime

log = logging.getLogger(__name__)

def clean_session_analyses(session, fw):
    
    gears = ['gambas', 'recon-all-clinical']
    for gear in gears:
        query = f"session._id = {session.id} AND analysis.label CONTAINS {gear}"

        gear_results = fw.search(
            {"structured_query": query,
            "return_type":"analysis"}
        )
        gear_matches = [r.analysis.reload() for r in gear_results]
        for analysis in gear_matches:
            print(f"Deleting analysis {analysis.label} from session {session.label}")
            try:
                fw.delete_analysis(analysis.id)
            except Exception as e:
                print(f"Error deleting analysis {analysis.label} from session {session.label}: {e}")

    #Clean recon-all-clinical and gambas analyses if any
    for analysis in session.analyses:
        if analysis.gear_info is not None and analysis.gear_info.name in ['recon-all-clinical', 'gambas']:
            print(f"Deleting analysis {analysis.label} of type {analysis.gear_info.name} from session {session.label}")
            fw.delete_analysis(analysis.id)
        else:
            print(f"Skipping analysis {analysis.label} of type {analysis.gear_info.name if analysis.gear_info else 'Unknown'}")

def is_ghost_analysis(analysis):
    """
    Check if an analysis is a ghost analysis by checking gear name or analysis label.
    """
    # Check gear name - must be exactly 'ghost' gear
    if analysis.label:
        label = analysis.label.lower()
        # Look for patterns like 'gambas/0.4.14' or 'gambas/0.4.17'
        if ("ghost/" in label and analysis.files) or (analysis.gear_info is not None and analysis.gear_info.name.lower() == "ghost" and analysis.job.get('state') == "complete"):
            return True
        
    return False

def submit_ghost_job(session, fw):
    gear =  fw.lookup('gears/ghost')
    analysis_tag = 'ghost'

    job_list = list()
    ghost_analyses = [analysis for analysis in session.analyses if is_ghost_analysis(analysis)]
    if ghost_analyses:
        print(f"Skipping session {session.label} - ghost analysis already exists.")
        return
    try:
        # The destination for this analysis will be on the session
        dest = session
        time_fmt = '%d-%m-%Y_%H-%M-%S'
        analysis_label = f'{analysis_tag}_{datetime.now().strftime(time_fmt)}'
        job_id = gear.run(
            analysis_label=analysis_label,
            
            destination=dest,
            tags=["analysis", "ghost","gpu"],
            config={
            
                }
        )
        job_list.append(job_id)
        print("Submitting Job: Check Jobs Log", dest.label)
    except Exception as e:
        print(f"WARNING: Job cannot be sent for {dest.label}. Error: {e}")

def find_files():

    """Runs the phantom curation algorithm.

    Args:
        input_image: FISP acquistion dicom.
    
    Returns:
    output_dir: Phantom QA project.


    """

    log.info("Starting the process curation process...")
    
    # Read config.json file
    p = open('/flywheel/v0/config.json')
    config = json.loads(p.read())

    # Read API key in config file
    api_key = (config['inputs']['api-key']['key'])
    fw = flywheel.Client(api_key=api_key)

    # Get the Phantom QA project
    phantom = fw.lookup("dev/Phantom_QA")

    # Get the parent id from inputs in config file
    input_container_type = config.get("inputs", {}).get("dicom-input", {}).get("hierarchy", {}).get("type")
    if input_container_type == 'session':
        session_id = config.get("inputs", {}).get("dicom-input", {}).get("hierarchy", {}).get("id")
        session_container = fw.get(session_id)
        print("running from session level...")
        print("session_container is : ", session_container.label)

        project_id = session_container.parents.project
        project = fw.get(project_id)
        print("project_container is : ", project.label)
        
    else:
        parent_id = config.get("inputs", {}).get("dicom-input", {}).get("hierarchy", {}).get("id")
        parent = fw.get(parent_id)
        print(parent.parents)
        project_id = parent.parents.project
        project = fw.get(project_id)
        print("project_container is : ", project.label)

    for subject in project.subjects.iter():
        subLabel = subject.label
        if subLabel.startswith('137-00') or subLabel.startswith('13700') or subLabel.startswith('137_00'):
            print("Looks like a phantom scan: ", subLabel)
            
            for session in subject.sessions.iter():
                print("session: ", session.label)
                # Add a tag to a session
                session.add_tag('Phantom')

                # Create new subject in Phantom QA project
                try:
                    phantom_subject = phantom.add_subject(label=subject.label)                                
                except:
                    # If subject already exists, reload it
                    phantom_subject = phantom.subjects.find_one("label=" + subject.label)
                    
                # Move session to Phantom QA project
                dest_sub = phantom_subject.reload()
                try:
                    print("Moving session: ", session.label)
                    session.update({'subject': dest_sub.id})
                    #Clear session analyses if any and schedule ghost analysis with helper functions
                    submit_ghost_job(session, fw)
                    clean_session_analyses(session, fw)
                except:
                    print("Error moving session")
                    continue
    log.info("Exiting main...")
    return 0

