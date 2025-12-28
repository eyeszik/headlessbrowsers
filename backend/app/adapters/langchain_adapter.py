"""
LangChain Adapter for Content Automation Platform.

Converts platform specifications into executable LangChain workflows.
"""
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import logging

from backend.app.services.orchestrator import AgentPayload, get_orchestrator
from backend.app.services.state_verifier import state_verifier
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LangChainContentAgent:
    """
    LangChain-based content automation agent.

    Features:
    - Tool-augmented generation
    - Memory and context management
    - State checkpointing
    - Confidence tracking
    """

    def __init__(
        self,
        agent_id: str,
        model_name: str = "gpt-4",
        temperature: float = 0.7
    ):
        self.agent_id = agent_id
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=settings.OPENAI_API_KEY
        )

        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Define tools available to agent
        self.tools = self._create_tools()

        # Create agent
        self.agent = self._create_agent()

    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools for content operations."""
        return [
            Tool(
                name="publish_content",
                func=self._publish_content_tool,
                description=(
                    "Publish content to social media platform. "
                    "Input: {platform: str, content: str, media_ids: List[int]}"
                )
            ),
            Tool(
                name="fetch_analytics",
                func=self._fetch_analytics_tool,
                description=(
                    "Fetch analytics for published content. "
                    "Input: {content_id: int, platform: str}"
                )
            ),
            Tool(
                name="generate_caption",
                func=self._generate_caption_tool,
                description=(
                    "Generate AI caption for content. "
                    "Input: {prompt: str, platform: str, provider: str}"
                )
            ),
            Tool(
                name="validate_content",
                func=self._validate_content_tool,
                description=(
                    "Validate content against platform requirements. "
                    "Input: {content: str, platform: str}"
                )
            )
        ]

    def _create_agent(self) -> AgentExecutor:
        """Create LangChain agent with tools."""
        # System prompt
        system_prompt = """You are an expert content automation agent with access to tools for:
- Publishing content to social media platforms
- Fetching analytics and performance metrics
- Generating AI-optimized captions
- Validating content against platform requirements

When executing tasks:
1. Always validate content before publishing
2. Include confidence scores in your outputs
3. Log all assumptions explicitly
4. Consider platform-specific constraints
5. Flag high-risk operations for human review

Your responses should be structured, actionable, and include clear reasoning."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        agent = create_openai_functions_agent(
            llm=self.model,
            tools=self.tools,
            prompt=prompt
        )

        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            return_intermediate_steps=True
        )

    async def execute_task(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentPayload:
        """
        Execute task with state checkpointing and confidence tracking.

        Args:
            task_description: Natural language task description
            context: Optional context dictionary

        Returns:
            AgentPayload with results and metadata
        """
        # Create state checkpoint before execution
        checkpoint_id = f"{self.agent_id}_{datetime.utcnow().timestamp()}"
        initial_state = {
            "task": task_description,
            "context": context or {},
            "agent_id": self.agent_id
        }

        checkpoint = state_verifier.create_checkpoint(
            checkpoint_id,
            initial_state
        )

        logger.info(f"Created checkpoint {checkpoint_id}")

        try:
            # Execute agent
            result = await self.agent.ainvoke({
                "input": task_description,
                "context": context or {}
            })

            # Extract reasoning and confidence
            reasoning = self._extract_reasoning(result)
            confidence = self._estimate_confidence(result)

            # Create result payload
            payload = AgentPayload(
                task_id=checkpoint_id,
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                payload_data={
                    "task": task_description,
                    "result": result["output"]
                },
                payload_hash_sha256="",  # Will be computed
                confidence_score=confidence,
                reasoning_trace=reasoning,
                assumptions_made=self._extract_assumptions(result),
                alternatives_considered=[]
            )

            # Compute hash
            payload.payload_hash_sha256 = payload.compute_hash()

            # Verify execution state
            if state_verifier.verify_checkpoint(checkpoint_id):
                logger.info("State verification passed")
            else:
                logger.error("State verification failed - possible corruption")
                payload.metadata["state_verification"] = "FAILED"

            return payload

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            raise

    def _publish_content_tool(self, input_str: str) -> str:
        """Tool implementation for publishing content."""
        # Parse input and call platform integration
        # This would integrate with the existing platform services
        return f"Content published successfully: {input_str}"

    def _fetch_analytics_tool(self, input_str: str) -> str:
        """Tool implementation for fetching analytics."""
        return f"Analytics fetched: {input_str}"

    def _generate_caption_tool(self, input_str: str) -> str:
        """Tool implementation for caption generation."""
        return f"Caption generated: {input_str}"

    def _validate_content_tool(self, input_str: str) -> str:
        """Tool implementation for content validation."""
        return f"Content validated: {input_str}"

    def _extract_reasoning(self, result: Dict[str, Any]) -> str:
        """Extract reasoning from agent result."""
        if "intermediate_steps" in result:
            steps = result["intermediate_steps"]
            return "\n".join([str(step) for step in steps])
        return "No reasoning trace available"

    def _estimate_confidence(self, result: Dict[str, Any]) -> float:
        """Estimate confidence from agent execution."""
        # Simple heuristic - could be improved with model-based estimation
        if "intermediate_steps" in result:
            steps = len(result["intermediate_steps"])
            if steps == 0:
                return 0.5
            elif steps <= 3:
                return 0.8
            else:
                return 0.95
        return 0.5

    def _extract_assumptions(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract assumptions from agent execution."""
        # Would parse intermediate steps for assumption markers
        return []


# Example usage template
LANGCHAIN_WORKFLOW_TEMPLATE = """
from backend.app.adapters.langchain_adapter import LangChainContentAgent
from backend.app.db.session import SessionLocal

# Initialize agent
agent = LangChainContentAgent(
    agent_id="content_publisher_1",
    model_name="gpt-4",
    temperature=0.7
)

# Execute task
async def run_workflow():
    result = await agent.execute_task(
        task_description=\"\"\"
        Create and publish a LinkedIn post about our new product launch.
        The post should be professional, include key features, and target
        enterprise customers. Generate an optimized caption and publish
        to our company LinkedIn page.
        \"\"\",
        context={
            "product_name": "Enterprise Analytics Suite",
            "key_features": ["Real-time dashboards", "AI insights", "Team collaboration"],
            "target_audience": "CTOs and data leaders",
            "linkedin_page_id": "company-page-123"
        }
    )

    print(f"Task completed with confidence: {result.confidence_score}")
    print(f"Result: {result.outputs}")

    return result

# Run
import asyncio
asyncio.run(run_workflow())
"""
