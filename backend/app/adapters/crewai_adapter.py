"""
CrewAI Adapter for Content Automation Platform.

Defines multi-agent crews for complex content workflows.
"""
from typing import List, Dict, Any, Optional
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import logging

from backend.app.core.config import settings
from backend.app.services.orchestrator import AgentRole

logger = logging.getLogger(__name__)


class ContentAutomationCrew:
    """
    CrewAI-based multi-agent content automation system.

    Agents:
    - Content Strategist: Plans content strategy
    - Content Creator: Generates content
    - Quality Validator: Validates outputs
    - Adversarial Reviewer: Challenges assumptions
    - Analytics Analyst: Interprets metrics
    """

    def __init__(self, model_name: str = "gpt-4"):
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.OPENAI_API_KEY
        )

        self.agents = self._create_agents()
        self.crew = self._create_crew()

    def _create_agents(self) -> Dict[str, Agent]:
        """Create specialized agents for content workflow."""
        return {
            "strategist": Agent(
                role="Content Strategist",
                goal="Plan effective content strategies aligned with campaign goals",
                backstory="""You are an expert content strategist with deep knowledge
                of social media platforms, audience engagement, and content optimization.
                You analyze campaign objectives and create detailed content plans.""",
                llm=self.llm,
                verbose=True,
                allow_delegation=True
            ),

            "creator": Agent(
                role="Content Creator",
                goal="Generate high-quality, platform-optimized content",
                backstory="""You are a creative content writer skilled in crafting
                engaging posts for multiple social media platforms. You understand
                platform-specific best practices and optimize for engagement.""",
                llm=self.llm,
                verbose=True,
                allow_delegation=False
            ),

            "validator": Agent(
                role="Quality Validator",
                goal="Ensure content meets quality standards and platform requirements",
                backstory="""You are a meticulous quality assurance specialist who
                validates content against platform guidelines, brand voice, and
                campaign objectives. You identify issues and suggest improvements.""",
                llm=self.llm,
                verbose=True,
                allow_delegation=False
            ),

            "adversarial": Agent(
                role="Adversarial Reviewer",
                goal="Challenge assumptions and identify potential issues",
                backstory="""You are a critical thinker who questions assumptions
                and identifies edge cases. Your role is to prevent groupthink and
                ensure robust decision-making by proposing alternatives and highlighting risks.""",
                llm=self.llm,
                verbose=True,
                allow_delegation=False
            ),

            "analyst": Agent(
                role="Analytics Analyst",
                goal="Interpret performance metrics and provide actionable insights",
                backstory="""You are a data analyst specialized in social media
                metrics. You interpret analytics, identify trends, and provide
                recommendations for content optimization.""",
                llm=self.llm,
                verbose=True,
                allow_delegation=False
            )
        }

    def _create_crew(self) -> Crew:
        """Create crew with hierarchical process."""
        return Crew(
            agents=list(self.agents.values()),
            process=Process.hierarchical,
            manager_llm=self.llm,
            verbose=True
        )

    def create_content_campaign(
        self,
        campaign_brief: str,
        platforms: List[str],
        target_audience: str,
        kpi_targets: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute complete content campaign workflow.

        Workflow:
        1. Strategist plans content approach
        2. Creator generates content variants
        3. Validator checks quality
        4. Adversarial reviews assumptions
        5. Final approval and scheduling

        Args:
            campaign_brief: Campaign description
            platforms: Target platforms
            target_audience: Audience description
            kpi_targets: Success metrics

        Returns:
            Campaign execution results
        """
        # Define tasks
        tasks = [
            Task(
                description=f"""Analyze the campaign brief and create a detailed
                content strategy for {', '.join(platforms)} targeting {target_audience}.

                Campaign Brief: {campaign_brief}

                Your strategy should include:
                - Platform-specific content themes
                - Posting schedule recommendations
                - Key messages and tone
                - Hashtag strategy
                - Expected KPIs: {kpi_targets}

                Output a structured content plan with clear rationale.""",
                agent=self.agents["strategist"],
                expected_output="Structured content strategy with platform-specific recommendations"
            ),

            Task(
                description="""Based on the content strategy, create 5 content variants
                optimized for each platform. Each variant should:
                - Match platform character limits and best practices
                - Include appropriate hashtags
                - Maintain consistent brand voice
                - Target specified audience
                - Include confidence scores for each variant

                For each variant, explain your creative decisions.""",
                agent=self.agents["creator"],
                expected_output="5 platform-optimized content variants with reasoning"
            ),

            Task(
                description="""Validate all content variants against:
                - Platform requirements (character limits, hashtag rules)
                - Brand voice consistency
                - Grammar and spelling
                - Engagement potential
                - Compliance with policies

                For each variant, provide:
                - Quality score (0-100)
                - Identified issues
                - Improvement recommendations
                - Final approval or rejection""",
                agent=self.agents["validator"],
                expected_output="Quality assessment for each variant with scores and recommendations"
            ),

            Task(
                description="""Review the content strategy and variants from an
                adversarial perspective. Identify:
                - Questionable assumptions
                - Potential risks or controversies
                - Edge cases not considered
                - Alternative approaches
                - What could go wrong

                Be constructively critical and propose alternatives.""",
                agent=self.agents["adversarial"],
                expected_output="Critical review identifying risks and proposing alternatives"
            )
        ]

        # Execute crew workflow
        result = self.crew.kickoff(tasks=tasks)

        return {
            "strategy": tasks[0].output,
            "content_variants": tasks[1].output,
            "quality_validation": tasks[2].output,
            "adversarial_review": tasks[3].output,
            "final_result": result
        }

    def analyze_campaign_performance(
        self,
        campaign_id: int,
        analytics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze campaign performance with AI insights.

        Args:
            campaign_id: Campaign identifier
            analytics_data: Aggregated analytics

        Returns:
            Analysis with insights and recommendations
        """
        analysis_task = Task(
            description=f"""Analyze the performance data for campaign {campaign_id}:

            {analytics_data}

            Provide:
            1. Performance summary (vs. KPI targets)
            2. Best performing content and why
            3. Underperforming content and reasons
            4. Platform-specific insights
            5. Actionable recommendations for optimization
            6. Confidence levels for each recommendation

            Be data-driven and specific.""",
            agent=self.agents["analyst"],
            expected_output="Comprehensive performance analysis with actionable recommendations"
        )

        result = self.crew.kickoff(tasks=[analysis_task])

        return {
            "analysis": result,
            "confidence_score": 0.85  # Would extract from analysis
        }


# Example CrewAI workflow template
CREWAI_WORKFLOW_TEMPLATE = """
from backend.app.adapters.crewai_adapter import ContentAutomationCrew

# Initialize crew
crew = ContentAutomationCrew(model_name="gpt-4")

# Execute campaign creation
result = crew.create_content_campaign(
    campaign_brief=\"\"\"
    Launch campaign for our new AI-powered analytics platform.
    Target enterprise customers who are data-driven and tech-savvy.
    Focus on unique features: real-time insights, predictive analytics,
    and seamless integrations.
    \"\"\",
    platforms=["linkedin", "twitter", "facebook"],
    target_audience="CTOs, Data Leaders, Enterprise Decision Makers",
    kpi_targets={
        "impressions": 50000,
        "engagement_rate": 3.5,
        "conversions": 100
    }
)

# Review results
print("Content Strategy:")
print(result["strategy"])

print("\\nContent Variants:")
print(result["content_variants"])

print("\\nQuality Validation:")
print(result["quality_validation"])

print("\\nAdversarial Review:")
print(result["adversarial_review"])

# After campaign runs, analyze performance
performance = crew.analyze_campaign_performance(
    campaign_id=123,
    analytics_data={
        "total_impressions": 75000,
        "engagement_rate": 4.2,
        "conversions": 145,
        "platform_breakdown": {
            "linkedin": {"impressions": 45000, "engagement": 5.1},
            "twitter": {"impressions": 20000, "engagement": 3.8},
            "facebook": {"impressions": 10000, "engagement": 2.5}
        }
    }
)

print("\\nPerformance Analysis:")
print(performance["analysis"])
"""
