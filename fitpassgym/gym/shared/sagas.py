"""Saga pattern implementation for multi-step distributed workflows.

A saga is a sequence of local transactions where each transaction updates
data within a single service. If a transaction fails, the saga triggers
compensating transactions to undo the changes of preceding transactions.

This implementation supports both choreography (event-driven) and orchestration
(centralized coordination) patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from django.utils import timezone


class SagaStatus(Enum):
    """Status of a saga execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"


class SagaStepStatus(Enum):
    """Status of a saga step."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """Represents a single step in a saga."""
    
    name: str
    action: callable
    compensation: callable
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def __hash__(self):
        return hash(self.name)


@dataclass
class SagaDefinition:
    """Defines the sequence of steps in a saga."""
    
    name: str
    steps: List[SagaStep] = field(default_factory=list)
    
    def add_step(self, step: SagaStep) -> "SagaDefinition":
        """Add a step to the saga definition."""
        self.steps.append(step)
        return self


@dataclass
class SagaExecution:
    """Tracks the execution state of a saga."""
    
    saga_id: str
    definition: SagaDefinition
    status: SagaStatus = SagaStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    step_results: Dict[str, Any] = field(default_factory=dict)
    compensated_steps: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if saga has completed."""
        return self.status in {SagaStatus.COMPLETED, SagaStatus.FAILED}


class SagaOrchestrator(ABC):
    """Orchestrates saga execution with error handling and compensation."""
    
    def __init__(self):
        self._executions: Dict[str, SagaExecution] = {}
        self._step_index: Dict[str, int] = {}
    
    def start_saga(
        self,
        saga_id: str,
        definition: SagaDefinition,
        context: Dict[str, Any],
    ) -> SagaExecution:
        """Start a new saga execution."""
        execution = SagaExecution(
            saga_id=saga_id,
            definition=definition,
            status=SagaStatus.IN_PROGRESS,
            started_at=timezone.now(),
        )
        self._executions[saga_id] = execution
        self._step_index[saga_id] = 0
        
        # Execute steps
        self._execute_steps(saga_id, execution, context)
        
        return execution
    
    def _execute_steps(
        self,
        saga_id: str,
        execution: SagaExecution,
        context: Dict[str, Any],
    ) -> None:
        """Execute all steps in the saga."""
        try:
            for step_index, step in enumerate(execution.definition.steps):
                if execution.status == SagaStatus.FAILED:
                    break
                
                step.status = SagaStepStatus.EXECUTING
                self._step_index[saga_id] = step_index
                
                try:
                    # Execute the step's action
                    result = step.action(context, execution.step_results)
                    step.result = result
                    execution.step_results[step.name] = result
                    step.status = SagaStepStatus.COMPLETED
                except Exception as e:
                    step.status = SagaStepStatus.FAILED
                    step.error = str(e)
                    execution.status = SagaStatus.FAILED
                    execution.error = str(e)
                    
                    # Trigger compensation
                    self._compensate_steps(saga_id, execution, step_index, context)
                    return
            
            # All steps completed successfully
            execution.status = SagaStatus.COMPLETED
            execution.completed_at = timezone.now()
        
        except Exception as e:
            execution.status = SagaStatus.FAILED
            execution.error = str(e)
            self._compensate_steps(saga_id, execution, len(execution.definition.steps), context)
    
    def _compensate_steps(
        self,
        saga_id: str,
        execution: SagaExecution,
        failed_step_index: int,
        context: Dict[str, Any],
    ) -> None:
        """Execute compensating transactions for failed steps."""
        execution.status = SagaStatus.COMPENSATING
        
        # Execute compensation in reverse order
        for step_index in range(failed_step_index - 1, -1, -1):
            step = execution.definition.steps[step_index]
            if step.status == SagaStepStatus.COMPLETED:
                step.status = SagaStepStatus.COMPENSATING
                try:
                    step.compensation(context, step.result)
                    step.status = SagaStepStatus.COMPENSATED
                    execution.compensated_steps.append(step.name)
                except Exception as e:
                    # Log compensation error but continue with other compensations
                    step.error = f"Compensation failed: {str(e)}"
        
        # After compensation is complete, mark the saga as failed
        execution.status = SagaStatus.FAILED
        execution.completed_at = timezone.now()
    
    def get_execution(self, saga_id: str) -> Optional[SagaExecution]:
        """Retrieve a saga execution by ID."""
        return self._executions.get(saga_id)
    
    def get_all_executions(self) -> Dict[str, SagaExecution]:
        """Get all saga executions."""
        return dict(self._executions)


class SagaBuilder:
    """Builder for creating saga definitions with fluent API."""
    
    def __init__(self, saga_name: str):
        self.definition = SagaDefinition(name=saga_name)
    
    def add_step(
        self,
        name: str,
        action: callable,
        compensation: callable,
    ) -> "SagaBuilder":
        """Add a step to the saga."""
        step = SagaStep(
            name=name,
            action=action,
            compensation=compensation,
        )
        self.definition.add_step(step)
        return self
    
    def build(self) -> SagaDefinition:
        """Build the saga definition."""
        if not self.definition.steps:
            raise ValueError("Saga must have at least one step")
        return self.definition


# Global saga orchestrator instance
_saga_orchestrator: Optional[SagaOrchestrator] = None


def get_saga_orchestrator() -> SagaOrchestrator:
    """Get the global saga orchestrator instance."""
    global _saga_orchestrator
    if _saga_orchestrator is None:
        _saga_orchestrator = SagaOrchestrator()
    return _saga_orchestrator


def reset_saga_orchestrator() -> None:
    """Reset the global saga orchestrator (for testing)."""
    global _saga_orchestrator
    _saga_orchestrator = None
