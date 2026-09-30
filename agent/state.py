from typing import TypedDict, List, Dict, Any

class FollowUpState(TypedDict):
    customers: List[Dict[str, Any]]      # selected customers passed in
    generated_emails: List[Dict[str, Any]]  # output of node 1
    reviewed_emails: List[Dict[str, Any]]   # output of node 2 (human edited)
    sent_results: List[Dict[str, Any]]      # output of node 3 (send status)