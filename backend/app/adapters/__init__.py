"""Framework adapters for Content Automation Platform."""
from .langchain_adapter import LangChainContentAgent, LANGCHAIN_WORKFLOW_TEMPLATE
from .crewai_adapter import ContentAutomationCrew, CREWAI_WORKFLOW_TEMPLATE

__all__ = [
    "LangChainContentAgent",
    "ContentAutomationCrew",
    "LANGCHAIN_WORKFLOW_TEMPLATE",
    "CREWAI_WORKFLOW_TEMPLATE",
]
