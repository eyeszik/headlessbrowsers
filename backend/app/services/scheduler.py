"""
DAG-based task scheduler with topological sorting and dependency management.

Implements:
- Topological sort for task ordering
- Dependency resolution
- Exponential backoff retry
- State management with rollback
- Error boundaries
"""
from typing import Dict, List, Set, Optional, Any, Callable
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio
import logging
import hashlib
import json

from backend.app.models.models import (
    Content,
    TaskState,
    TaskStatus,
    ContentStatus
)
from backend.app.db.session import SessionLocal
from backend.app.crud.crud import crud_content, crud_task_state

logger = logging.getLogger(__name__)


class DAGScheduler:
    """
    DAG-based task scheduler for content publishing.

    Features:
    - Topological sorting for dependency resolution
    - Parallel task execution where possible
    - Automatic retry with exponential backoff
    - State persistence and rollback
    - Error isolation (error boundaries)
    """

    def __init__(self):
        self.retry_delays = [2, 4, 8]  # Exponential backoff in seconds

    def topological_sort(
        self,
        tasks: List[Content]
    ) -> List[List[Content]]:
        """
        Perform topological sort on content tasks.

        Args:
            tasks: List of Content objects with dependencies

        Returns:
            List of task levels (each level can be executed in parallel)

        Raises:
            ValueError: If circular dependency detected
        """
        # Build adjacency list and in-degree map
        task_map = {task.id: task for task in tasks}
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        # Initialize in-degree for all tasks
        for task in tasks:
            if task.id not in in_degree:
                in_degree[task.id] = 0

        # Build graph
        for task in tasks:
            if task.depends_on:
                for dep_id in task.depends_on:
                    if dep_id in task_map:
                        graph[dep_id].append(task.id)
                        in_degree[task.id] += 1

        # Find tasks with no dependencies (in-degree = 0)
        queue = deque([
            task_id for task_id in task_map.keys()
            if in_degree[task_id] == 0
        ])

        levels = []
        processed = 0

        while queue:
            # All tasks in current queue can be executed in parallel
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                task_id = queue.popleft()
                current_level.append(task_map[task_id])
                processed += 1

                # Reduce in-degree for dependent tasks
                for dependent_id in graph[task_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            levels.append(current_level)

        # Check for circular dependencies
        if processed != len(tasks):
            raise ValueError("Circular dependency detected in task DAG")

        return levels

    async def execute_dag(
        self,
        tasks: List[Content],
        dag_id: str,
        executor: Callable
    ) -> Dict[str, Any]:
        """
        Execute DAG of content tasks.

        Args:
            tasks: List of Content objects
            dag_id: Unique DAG identifier
            executor: Async function to execute each task

        Returns:
            Dict with execution results
        """
        # Perform topological sort
        try:
            levels = self.topological_sort(tasks)
        except ValueError as e:
            logger.error(f"DAG sorting failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "completed_tasks": []
            }

        logger.info(f"DAG {dag_id} has {len(levels)} levels")

        completed_tasks = []
        failed_tasks = []

        # Execute level by level
        for level_idx, level in enumerate(levels):
            logger.info(
                f"Executing level {level_idx + 1}/{len(levels)} "
                f"with {len(level)} tasks"
            )

            # Execute tasks in parallel within the level
            results = await asyncio.gather(
                *[
                    self._execute_task_with_retry(
                        task,
                        dag_id,
                        executor
                    )
                    for task in level
                ],
                return_exceptions=True
            )

            # Process results
            for task, result in zip(level, results):
                if isinstance(result, Exception):
                    logger.error(f"Task {task.id} failed: {result}")
                    failed_tasks.append({
                        "task_id": task.id,
                        "error": str(result)
                    })

                    # Check if we should halt DAG execution
                    if not self._should_continue_on_error(task):
                        logger.error(
                            f"Error boundary triggered. Halting DAG execution."
                        )
                        return {
                            "success": False,
                            "error": f"Task {task.id} failed with error boundary",
                            "completed_tasks": completed_tasks,
                            "failed_tasks": failed_tasks
                        }
                else:
                    completed_tasks.append(result)

        return {
            "success": len(failed_tasks) == 0,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "total_tasks": len(tasks)
        }

    async def _execute_task_with_retry(
        self,
        task: Content,
        dag_id: str,
        executor: Callable
    ) -> Dict[str, Any]:
        """
        Execute a single task with exponential backoff retry.

        Args:
            task: Content object
            dag_id: DAG identifier
            executor: Async function to execute the task

        Returns:
            Execution result
        """
        task_id = f"{dag_id}_{task.id}"

        # Create or update task state
        with SessionLocal() as db:
            task_state = crud_task_state.get_by_task_id(db, task_id)

            if not task_state:
                task_state = crud_task_state.create(db, {
                    "task_id": task_id,
                    "task_name": task.title,
                    "dag_id": dag_id,
                    "dependencies": task.depends_on,
                    "status": TaskStatus.PENDING,
                    "max_retries": task.max_retries
                })

            # Update to running
            crud_task_state.update_status(db, task_id, TaskStatus.RUNNING)

        # Execute with retry
        last_exception = None

        for attempt in range(task.max_retries + 1):
            try:
                logger.info(f"Executing task {task_id} (attempt {attempt + 1})")

                # Verify payload integrity
                if task.payload_hash:
                    if not task.verify_payload_integrity():
                        raise ValueError("Payload integrity check failed")

                # Execute the task
                result = await executor(task)

                # Success - update state
                with SessionLocal() as db:
                    crud_task_state.update_status(
                        db, task_id, TaskStatus.SUCCESS
                    )
                    crud_content.update_status(
                        db, task.id, ContentStatus.PUBLISHED
                    )

                return result

            except Exception as e:
                last_exception = e
                logger.error(
                    f"Task {task_id} attempt {attempt + 1} failed: {e}"
                )

                if attempt < task.max_retries:
                    # Exponential backoff
                    delay = self.retry_delays[min(
                        attempt,
                        len(self.retry_delays) - 1
                    )]

                    logger.info(f"Retrying in {delay}s...")

                    with SessionLocal() as db:
                        crud_task_state.update_status(
                            db, task_id, TaskStatus.RETRYING
                        )
                        crud_content.increment_retry(db, task.id)

                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    logger.error(
                        f"Task {task_id} failed after {task.max_retries + 1} attempts"
                    )

                    with SessionLocal() as db:
                        crud_task_state.update_status(
                            db, task_id, TaskStatus.FAILED, str(last_exception)
                        )
                        crud_content.update_status(
                            db, task.id, ContentStatus.FAILED, str(last_exception)
                        )

        raise last_exception

    def _should_continue_on_error(self, task: Content) -> bool:
        """
        Determine if DAG should continue when task fails.

        Args:
            task: Failed task

        Returns:
            True if DAG should continue
        """
        # Check task state for error boundary setting
        task_id = f"{task.id}"

        with SessionLocal() as db:
            task_state = crud_task_state.get_by_task_id(db, task_id)

            if task_state:
                return task_state.error_boundary

        # Default: halt on error
        return False

    async def rollback_task(
        self,
        task: Content,
        rollback_executor: Optional[Callable] = None
    ) -> bool:
        """
        Rollback a task to previous state.

        Args:
            task: Content object to rollback
            rollback_executor: Optional custom rollback function

        Returns:
            True if rollback successful
        """
        logger.info(f"Rolling back task {task.id}")

        try:
            if rollback_executor:
                await rollback_executor(task)
            elif task.rollback_data:
                # Restore from rollback data
                with SessionLocal() as db:
                    # Restore previous state
                    for field, value in task.rollback_data.items():
                        setattr(task, field, value)

                    db.add(task)
                    db.commit()

            # Update task state
            task_id = f"{task.id}"
            with SessionLocal() as db:
                crud_task_state.update_status(
                    db, task_id, TaskStatus.ROLLED_BACK
                )

            logger.info(f"Task {task.id} rolled back successfully")
            return True

        except Exception as e:
            logger.error(f"Rollback failed for task {task.id}: {e}")
            return False

    def compute_payload_hash(self, content: Content) -> str:
        """
        Compute SHA-256 hash of content payload.

        Args:
            content: Content object

        Returns:
            SHA-256 hash string
        """
        payload = {
            "title": content.title,
            "body": content.body,
            "media_ids": content.media_ids or [],
            "platform": content.platform.value
        }

        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def validate_dag(self, tasks: List[Content]) -> Dict[str, Any]:
        """
        Validate DAG structure.

        Args:
            tasks: List of Content objects

        Returns:
            Validation result
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "task_count": len(tasks),
            "max_depth": 0
        }

        # Check for circular dependencies
        try:
            levels = self.topological_sort(tasks)
            result["max_depth"] = len(levels)
        except ValueError as e:
            result["valid"] = False
            result["errors"].append(str(e))
            return result

        # Check for missing dependencies
        task_ids = {task.id for task in tasks}
        for task in tasks:
            if task.depends_on:
                missing = set(task.depends_on) - task_ids
                if missing:
                    result["warnings"].append(
                        f"Task {task.id} has missing dependencies: {missing}"
                    )

        return result


# Global instance
dag_scheduler = DAGScheduler()
