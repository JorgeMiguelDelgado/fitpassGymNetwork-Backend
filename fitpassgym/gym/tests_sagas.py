"""Tests for saga pattern implementation."""

from django.test import SimpleTestCase
from django.utils import timezone

from fitpassgym.gym.shared.sagas import (
    SagaBuilder,
    SagaDefinition,
    SagaExecution,
    SagaOrchestrator,
    SagaStatus,
    SagaStepStatus,
    get_saga_orchestrator,
    reset_saga_orchestrator,
)


class SagaBuilderTests(SimpleTestCase):
    """Test SagaBuilder fluent API."""
    
    def test_build_saga_with_single_step(self):
        """Test building a saga with a single step."""
        def action(context, results):
            return "step1_result"
        
        def compensation(context, result):
            pass
        
        saga = SagaBuilder("test_saga").add_step("step1", action, compensation).build()
        
        self.assertEqual(saga.name, "test_saga")
        self.assertEqual(len(saga.steps), 1)
        self.assertEqual(saga.steps[0].name, "step1")
    
    def test_build_saga_with_multiple_steps(self):
        """Test building a saga with multiple steps."""
        def action(context, results):
            return "result"
        
        def compensation(context, result):
            pass
        
        saga = (
            SagaBuilder("multi_step")
            .add_step("step1", action, compensation)
            .add_step("step2", action, compensation)
            .add_step("step3", action, compensation)
            .build()
        )
        
        self.assertEqual(len(saga.steps), 3)
        self.assertEqual(saga.steps[0].name, "step1")
        self.assertEqual(saga.steps[2].name, "step3")
    
    def test_build_empty_saga_raises_error(self):
        """Test that building an empty saga raises error."""
        with self.assertRaises(ValueError):
            SagaBuilder("empty").build()


class SagaOrchestratorTests(SimpleTestCase):
    """Test SagaOrchestrator execution."""
    
    def setUp(self):
        self.orchestrator = SagaOrchestrator()
        self.executed_steps = []
        self.compensated_steps = []
    
    def tearDown(self):
        reset_saga_orchestrator()
    
    def test_execute_simple_saga(self):
        """Test executing a simple successful saga."""
        def step1_action(context, results):
            self.executed_steps.append("step1")
            return {"value": 10}
        
        def step1_compensation(context, result):
            self.compensated_steps.append("step1")
        
        def step2_action(context, results):
            self.executed_steps.append("step2")
            return {"value": results["step1"]["value"] + 5}
        
        def step2_compensation(context, result):
            self.compensated_steps.append("step2")
        
        saga = (
            SagaBuilder("simple_saga")
            .add_step("step1", step1_action, step1_compensation)
            .add_step("step2", step2_action, step2_compensation)
            .build()
        )
        
        execution = self.orchestrator.start_saga("saga1", saga, {})
        
        self.assertEqual(execution.status, SagaStatus.COMPLETED)
        self.assertEqual(len(self.executed_steps), 2)
        self.assertEqual(self.executed_steps, ["step1", "step2"])
        self.assertEqual(execution.step_results["step1"], {"value": 10})
        self.assertEqual(execution.step_results["step2"], {"value": 15})
    
    def test_saga_with_failed_step_compensates(self):
        """Test that saga compensates when a step fails."""
        def step1_action(context, results):
            self.executed_steps.append("step1")
            return {"value": 10}
        
        def step1_compensation(context, result):
            self.compensated_steps.append("step1")
        
        def step2_action(context, results):
            self.executed_steps.append("step2")
            raise ValueError("Step 2 failed")
        
        def step2_compensation(context, result):
            self.compensated_steps.append("step2")
        
        saga = (
            SagaBuilder("failing_saga")
            .add_step("step1", step1_action, step1_compensation)
            .add_step("step2", step2_action, step2_compensation)
            .build()
        )
        
        execution = self.orchestrator.start_saga("saga2", saga, {})
        
        self.assertEqual(execution.status, SagaStatus.FAILED)
        self.assertEqual(self.executed_steps, ["step1", "step2"])
        # Compensation should only run for step1 (in reverse order)
        self.assertEqual(self.compensated_steps, ["step1"])
        self.assertIn("Step 2 failed", execution.error)
    
    def test_saga_compensation_order(self):
        """Test that compensation runs in reverse order."""
        def action(step_name):
            def _action(context, results):
                self.executed_steps.append(step_name)
                return {"step": step_name}
            return _action
        
        def compensation(step_name):
            def _compensation(context, result):
                self.compensated_steps.append(step_name)
            return _compensation
        
        def failing_action(context, results):
            self.executed_steps.append("step3")
            raise Exception("Failed at step 3")
        
        saga = (
            SagaBuilder("reverse_compensation")
            .add_step("step1", action("step1"), compensation("step1"))
            .add_step("step2", action("step2"), compensation("step2"))
            .add_step("step3", failing_action, compensation("step3"))
            .build()
        )
        
        execution = self.orchestrator.start_saga("saga3", saga, {})
        
        self.assertEqual(execution.status, SagaStatus.FAILED)
        # Compensation should run in reverse: step2, then step1
        self.assertEqual(self.compensated_steps, ["step2", "step1"])
    
    def test_get_saga_execution(self):
        """Test retrieving a saga execution."""
        def action(context, results):
            return "result"
        
        def compensation(context, result):
            pass
        
        saga = SagaBuilder("test").add_step("step1", action, compensation).build()
        execution = self.orchestrator.start_saga("saga4", saga, {})
        
        retrieved = self.orchestrator.get_execution("saga4")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.saga_id, "saga4")
        self.assertEqual(retrieved.status, SagaStatus.COMPLETED)
    
    def test_get_all_executions(self):
        """Test retrieving all saga executions."""
        def action(context, results):
            return "result"
        
        def compensation(context, result):
            pass
        
        saga = SagaBuilder("test").add_step("step1", action, compensation).build()
        
        self.orchestrator.start_saga("saga1", saga, {})
        self.orchestrator.start_saga("saga2", saga, {})
        
        all_executions = self.orchestrator.get_all_executions()
        self.assertEqual(len(all_executions), 2)
        self.assertIn("saga1", all_executions)
        self.assertIn("saga2", all_executions)


class SagaContextPassingTests(SimpleTestCase):
    """Test context and result passing between saga steps."""
    
    def setUp(self):
        self.orchestrator = SagaOrchestrator()
    
    def tearDown(self):
        reset_saga_orchestrator()
    
    def test_context_passed_to_steps(self):
        """Test that context is passed to all steps."""
        received_context = []
        
        def step_action(context, results):
            received_context.append(context)
            return {"result": context.get("value", 0)}
        
        def step_compensation(context, result):
            pass
        
        saga = (
            SagaBuilder("context_test")
            .add_step("step1", step_action, step_compensation)
            .add_step("step2", step_action, step_compensation)
            .build()
        )
        
        context = {"value": 42, "user_id": 10}
        execution = self.orchestrator.start_saga("saga", saga, context)
        
        # Both steps should receive the same context
        self.assertEqual(len(received_context), 2)
        self.assertEqual(received_context[0], context)
        self.assertEqual(received_context[1], context)
    
    def test_results_passed_between_steps(self):
        """Test that previous step results are passed to next steps."""
        def step1_action(context, results):
            return 10
        
        def step1_compensation(context, result):
            pass
        
        def step2_action(context, results):
            # Should receive step1's result
            self.assertEqual(results["step1"], 10)
            return results["step1"] + 5
        
        def step2_compensation(context, result):
            pass
        
        def step3_action(context, results):
            # Should receive both step1 and step2 results
            self.assertEqual(results["step1"], 10)
            self.assertEqual(results["step2"], 15)
            return results["step2"] * 2
        
        def step3_compensation(context, result):
            pass
        
        saga = (
            SagaBuilder("results_test")
            .add_step("step1", step1_action, step1_compensation)
            .add_step("step2", step2_action, step2_compensation)
            .add_step("step3", step3_action, step3_compensation)
            .build()
        )
        
        execution = self.orchestrator.start_saga("saga", saga, {})
        
        self.assertEqual(execution.status, SagaStatus.COMPLETED)
        self.assertEqual(execution.step_results["step3"], 30)


class GlobalSagaOrchestratorTests(SimpleTestCase):
    """Test global saga orchestrator singleton."""
    
    def tearDown(self):
        reset_saga_orchestrator()
    
    def test_get_orchestrator_returns_same_instance(self):
        """Test that get_saga_orchestrator returns the same instance."""
        orchestrator1 = get_saga_orchestrator()
        orchestrator2 = get_saga_orchestrator()
        
        self.assertIs(orchestrator1, orchestrator2)
    
    def test_reset_orchestrator_creates_new_instance(self):
        """Test that reset_saga_orchestrator creates a fresh instance."""
        orchestrator1 = get_saga_orchestrator()
        
        def action(context, results):
            return "result"
        
        def compensation(context, result):
            pass
        
        saga = SagaBuilder("test").add_step("step1", action, compensation).build()
        orchestrator1.start_saga("saga1", saga, {})
        
        # After reset, should get a new instance with no executions
        reset_saga_orchestrator()
        orchestrator2 = get_saga_orchestrator()
        
        self.assertIsNot(orchestrator1, orchestrator2)
        self.assertEqual(len(orchestrator2.get_all_executions()), 0)
