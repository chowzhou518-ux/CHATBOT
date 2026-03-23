"""Performance testing and latency measurement for the RAG system."""

import time
import statistics
from typing import List, Dict, Any, Callable
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class PerformanceMetrics:
    """Performance metrics for a component."""
    operation_name: str
    latencies: List[float] = field(default_factory=list)
    errors: int = 0
    total_calls: int = 0

    @property
    def avg_latency(self) -> float:
        """Average latency in seconds."""
        if not self.latencies:
            return 0.0
        return statistics.mean(self.latencies)

    @property
    def median_latency(self) -> float:
        """Median latency in seconds."""
        if not self.latencies:
            return 0.0
        return statistics.median(self.latencies)

    @property
    def p95_latency(self) -> float:
        """95th percentile latency in seconds."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]

    @property
    def p99_latency(self) -> float:
        """99th percentile latency in seconds."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]

    @property
    def min_latency(self) -> float:
        """Minimum latency in seconds."""
        if not self.latencies:
            return 0.0
        return min(self.latencies)

    @property
    def max_latency(self) -> float:
        """Maximum latency in seconds."""
        if not self.latencies:
            return 0.0
        return max(self.latencies)

    @property
    def throughput(self) -> float:
        """Operations per second."""
        if self.total_calls == 0:
            return 0.0
        total_time = sum(self.latencies)
        if total_time == 0:
            return 0.0
        return self.total_calls / total_time

    @property
    def error_rate(self) -> float:
        """Error rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.errors / self.total_calls) * 100


class PerformanceMonitor:
    """Monitor performance of system components."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: Dict[str, PerformanceMetrics] = {}

    def track_latency(self, operation_name: str) -> Callable:
        """
        Decorator to track function latency.

        Args:
            operation_name: Name of the operation to track

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                error = False

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception:
                    error = True
                    raise
                finally:
                    latency = time.time() - start_time
                    self._record_latency(operation_name, latency, error)

            return wrapper
        return decorator

    def _record_latency(self, operation_name: str, latency: float, error: bool) -> None:
        """Record a latency measurement."""
        if operation_name not in self.metrics:
            self.metrics[operation_name] = PerformanceMetrics(operation_name)

        metric = self.metrics[operation_name]
        metric.total_calls += 1

        if not error:
            metric.latencies.append(latency)
        else:
            metric.errors += 1

    def get_metrics(self, operation_name: str) -> PerformanceMetrics:
        """Get metrics for a specific operation."""
        return self.metrics.get(operation_name, PerformanceMetrics(operation_name))

    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get all metrics."""
        return self.metrics.copy()

    def generate_report(self) -> str:
        """Generate a performance report."""
        if not self.metrics:
            return "No performance data collected."

        lines = [
            "=" * 70,
            "Performance Test Report",
            "=" * 70,
            "",
        ]

        for name, metric in sorted(self.metrics.items()):
            lines.extend([
                f"Operation: {name}",
                "-" * 70,
                f"  Total Calls: {metric.total_calls}",
                f"  Errors: {metric.errors} ({metric.error_rate:.2f}%)",
                f"",
                f"  Latency (seconds):",
                f"    Average: {metric.avg_latency*1000:.2f} ms",
                f"    Median: {metric.median_latency*1000:.2f} ms",
                f"    Min: {metric.min_latency*1000:.2f} ms",
                f"    Max: {metric.max_latency*1000:.2f} ms",
                f"    P95: {metric.p95_latency*1000:.2f} ms",
                f"    P99: {metric.p99_latency*1000:.2f} ms",
                f"",
                f"  Throughput: {metric.throughput:.2f} ops/sec",
                f"",
            ])

        return "\n".join(lines)


class RAGPerformanceTest:
    """Performance tests for RAG system."""

    def __init__(self):
        """Initialize performance tester."""
        self.monitor = PerformanceMonitor()
        self.test_queries = [
            "What are your working hours?",
            "How much does it cost to park?",
            "Where is the parking located?",
            "What types of spaces are available?",
            "How do I make a reservation?",
            "What payment methods do you accept?",
            "Are there EV charging stations?",
            "Is there accessible parking?",
            "What are the parking rules?",
            "Can I get a weekly pass?",
        ]

    def run_retrieval_test(self, num_iterations: int = 10) -> PerformanceMetrics:
        """
        Test vector store retrieval performance.

        Args:
            num_iterations: Number of test iterations

        Returns:
            Performance metrics for retrieval
        """
        from src.core.vector_store import get_vector_store

        vector_store = get_vector_store(use_in_memory=True)

        for _ in range(num_iterations):
            for query in self.test_queries:
                start = time.time()
                try:
                    results = vector_store.search(query, top_k=5)
                    latency = time.time() - start
                    self.monitor._record_latency("vector_search", latency, False)
                except Exception as e:
                    latency = time.time() - start
                    self.monitor._record_latency("vector_search", latency, True)

        return self.monitor.get_metrics("vector_search")

    def run_llm_test(self, num_iterations: int = 5) -> PerformanceMetrics:
        """
        Test LLM generation performance.

        Args:
            num_iterations: Number of test iterations

        Returns:
            Performance metrics for LLM
        """
        from src.core.llm_handler import LLMHandler

        llm_handler = LLMHandler()
        test_prompt = "What are your working hours?"

        for _ in range(num_iterations):
            start = time.time()
            try:
                response = llm_handler.generate_response(
                    prompt=test_prompt,
                    system_prompt="You are a parking assistant.",
                )
                latency = time.time() - start
                self.monitor._record_latency("llm_generation", latency, False)
            except Exception as e:
                latency = time.time() - start
                self.monitor._record_latency("llm_generation", latency, True)

        return self.monitor.get_metrics("llm_generation")

    def run_end_to_end_test(self, num_iterations: int = 5) -> PerformanceMetrics:
        """
        Test complete RAG pipeline performance.

        Args:
            num_iterations: Number of test iterations

        Returns:
            Performance metrics for end-to-end
        """
        from src.chatbot.agent import get_simple_chatbot

        chatbot = get_simple_chatbot()

        for _ in range(num_iterations):
            for query in self.test_queries:
                start = time.time()
                try:
                    response = chatbot.chat(query)
                    latency = time.time() - start
                    self.monitor._record_latency("end_to_end", latency, False)
                except Exception as e:
                    latency = time.time() - start
                    self.monitor._record_latency("end_to_end", latency, True)

        return self.monitor.get_metrics("end_to_end")

    def run_all_tests(self, num_iterations: int = 5) -> str:
        """
        Run all performance tests.

        Args:
            num_iterations: Number of iterations per test

        Returns:
            Performance report
        """
        print("Running performance tests...")

        print("  - Testing vector store retrieval...")
        self.run_retrieval_test(num_iterations)

        print("  - Testing LLM generation...")
        self.run_llm_test(num_iterations)

        print("  - Testing end-to-end pipeline...")
        self.run_end_to_end_test(num_iterations)

        return self.monitor.generate_report()


def benchmark_system() -> str:
    """
    Run comprehensive system benchmarks.

    Returns:
        Benchmark report as string.
    """
    tester = RAGPerformanceTest()
    return tester.run_all_tests(num_iterations=10)


def measure_guardrail_performance(num_tests: int = 100) -> str:
    """
    Measure guardrail filtering performance.

    Args:
        num_tests: Number of test inputs to process

    Returns:
        Performance report for guardrails
    """
    from src.guards.filters import get_pii_detector, get_input_sanitizer
    from src.guards.railguard import GuardRailHandler

    monitor = PerformanceMonitor()
    detector = get_pii_detector()
    sanitizer = get_input_sanitizer()
    guardrails = GuardRailHandler()

    # Test inputs
    test_inputs = [
        "What are your hours?",
        "My name is John Smith and my email is john@example.com",
        "Where are you located?",
        "Call me at 555-123-4567 for information",
        "How much is parking?",
        "My license plate is ABC-1234",
        "Are there spaces available?",
    ]

    # Test PII detection
    for _ in range(num_tests):
        for test_input in test_inputs:
            start = time.time()
            try:
                entities = detector.detect_pii(test_input)
                latency = time.time() - start
                monitor._record_latency("pii_detection", latency, False)
            except Exception:
                latency = time.time() - start
                monitor._record_latency("pii_detection", latency, True)

    # Test input sanitization
    for _ in range(num_tests):
        for test_input in test_inputs:
            start = time.time()
            try:
                sanitized = sanitizer.sanitize(test_input)
                latency = time.time() - start
                monitor._record_latency("input_sanitization", latency, False)
            except Exception:
                latency = time.time() - start
                monitor._record_latency("input_sanitization", latency, True)

    # Test full guardrail pipeline
    for _ in range(num_tests):
        for test_input in test_inputs:
            start = time.time()
            try:
                processed, error = guardrails.process_input(test_input)
                latency = time.time() - start
                monitor._record_latency("guardrail_pipeline", latency, False)
            except Exception:
                latency = time.time() - start
                monitor._record_latency("guardrail_pipeline", latency, True)

    return monitor.generate_report()


if __name__ == "__main__":
    # Run benchmarks when executed directly
    print("=" * 70)
    print("RAG System Performance Benchmarks")
    print("=" * 70)
    print()

    print(benchmark_system())
    print()
    print(measure_guardrail_performance())
