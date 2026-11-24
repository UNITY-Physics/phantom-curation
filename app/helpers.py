
def has_complete_ghost_analysis_with_files(session):
    """
    Check if the session has at least one complete ghost analysis with files.
    """
    has_successful_analysis = False

    for analysis in session.analyses:
        if analysis.gear_info and analysis.gear_info.name == "ghost":
            if analysis.job and (analysis.job.get("state") == "pending" or analysis.job.get("state") == "running" or (analysis.job.get("state") == "complete" and analysis.files) ):
                has_successful_analysis =  True
                print(f'Session {session.label} has a ghost analysis: {analysis.job.get("state")} - no need to rerun')
            elif (analysis.job and analysis.job.get("state") == "failed"):
                print(f"Session {session.label} has a failed ghost analysis: {analysis.label} - no need to rerun")
                has_successful_analysis =  True
        elif "ghost/" in analysis.label and analysis.files:
            has_successful_analysis =  True
    return has_successful_analysis



def acquisitions_have_files(session):
    complete = True
    for acq in session.acquisitions():
        acq = acq.reload()
        print(acq.label, " has ", len(acq.files), " files.")
        complete = complete and (len(acq.files) > 0)
        
    return complete


def clean_session_analyses(session, fw):
    
    gears = ["gambas"]
    analyses = fw.analyses.find(f"parents.session={session.id}")
    for asys in analyses:
        try:
            if asys.gear_info is not None and asys.gear_info.name not in gears:
                r = asys.reload()
                print(f"Deleting analysis {r.label} from session {session.label}")
                fw.delete_analysis(r.id, r.label)
        except Exception as e:
            print(f"Error deleting analysis {r.label} from session {session.label}: {e}")
