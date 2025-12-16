"""Message formatters for notifications."""
from typing import Optional


def format_pr_summary_card(
    pr_number: int,
    title: str,
    author: str,
    repo_name: str,
    state: str,
    files_changed: Optional[int] = None,
    additions: Optional[int] = None,
    deletions: Optional[int] = None,
    url: Optional[str] = None,
) -> dict:
    """Format PR summary as Google Chat card.
    
    Args:
        pr_number: PR number
        title: PR title
        author: PR author
        repo_name: Repository name
        state: PR state (open/closed)
        files_changed: Number of files changed
        additions: Lines added
        deletions: Lines deleted
        url: PR URL
        
    Returns:
        Google Chat card payload
    """
    header = {
        "title": f"PR #{pr_number}: {title}",
        "subtitle": f"{repo_name} · {author}",
    }
    
    sections = []
    
    # Summary section
    summary_text = f"State: {state}"
    if files_changed is not None:
        summary_text += f" | Files: {files_changed}"
    if additions is not None and deletions is not None:
        summary_text += f" | +{additions}/-{deletions} lines"
    
    sections.append({
        "widgets": [
            {
                "textParagraph": {
                    "text": summary_text,
                }
            }
        ]
    })
    
    # Link button if URL provided
    if url:
        sections.append({
            "widgets": [
                {
                    "buttons": [
                        {
                            "textButton": {
                                "text": "View PR",
                                "onClick": {
                                    "openLink": {
                                        "url": url,
                                    }
                                }
                            }
                        }
                    ]
                }
            ]
        })
    
    card = {
        "header": header,
        "sections": sections,
    }
    
    return card


def format_pr_findings_card(
    pr_number: int,
    title: str,
    repo_name: str,
    findings: list[dict],
    owners: Optional[list[dict]] = None,
    risk_score: Optional[float] = None,
    ttf_p50: Optional[float] = None,
    ttf_p90: Optional[float] = None,
) -> dict:
    """Format PR findings as Google Chat card (v2).
    
    Args:
        pr_number: PR number
        title: PR title
        repo_name: Repository name
        findings: List of findings with rule_id, severity, message
        owners: List of owner hints with name and confidence
        risk_score: Risk score (0-10)
        ttf_p50: Time to fix P50 in hours
        ttf_p90: Time to fix P90 in hours
        
    Returns:
        Google Chat card payload
    """
    header = {
        "title": f"PR #{pr_number}: {title}",
        "subtitle": repo_name,
    }
    
    sections = []
    
    # Risk and metrics section
    metrics_text = ""
    if risk_score is not None:
        metrics_text += f"Risk: {risk_score}/10"
    if ttf_p50 is not None and ttf_p90 is not None:
        metrics_text += f" | TTF(P50/P90): {ttf_p50}/{ttf_p90}h"
    
    if metrics_text:
        sections.append({
            "widgets": [
                {
                    "textParagraph": {
                        "text": metrics_text,
                    }
                }
            ]
        })
    
    # Owners section
    if owners:
        owners_text = "Suspected owners: " + ", ".join(
            [f"{o['name']} ({o['confidence']:.0%})" for o in owners[:3]]
        )
        sections.append({
            "widgets": [
                {
                    "textParagraph": {
                        "text": owners_text,
                    }
                }
            ]
        })
    
    # Findings section
    if findings:
        findings_text = "Rules violated:\n"
        for finding in findings[:5]:  # Limit to 5 findings
            severity = finding.get("severity", "unknown")
            rule_id = finding.get("rule_id", "unknown")
            findings_text += f"• {severity.upper()}: {rule_id}\n"
        
        sections.append({
            "widgets": [
                {
                    "textParagraph": {
                        "text": findings_text,
                    }
                }
            ]
        })
    
    card = {
        "header": header,
        "sections": sections,
    }
    
    return card

