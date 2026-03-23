"""Tests for evaluation and metrics functionality."""

import pytest
from unittest.mock import Mock, patch

from src.evaluation.metrics import (
    RetrievalMetrics,
    RAGEvaluator,
    QueryEvaluation,
    GroundTruthDataset,
)
from src.evaluation.performance import (
    PerformanceMetrics,
    PerformanceMonitor,
    RAGPerformanceTest,
)


class TestRetrievalMetrics:
    """Tests for retrieval metrics calculations."""

    def test_precision_at_k(self):
        """Test Precision@K calculation."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3", "doc5"}

        precision = RetrievalMetrics.precision_at_k(retrieved, relevant, 5)
        assert precision == 0.6  # 3 out of 5

    def test_precision_at_k_with_k(self):
        """Test Precision@K with specific k value."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3"}

        precision = RetrievalMetrics.precision_at_k(retrieved, relevant, 3)
        assert precision == pytest.approx(0.667, 0.01)  # 2 out of 3

    def test_recall_at_k(self):
        """Test Recall@K calculation."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc3", "doc4", "doc5"}

        recall = RetrievalMetrics.recall_at_k(retrieved, relevant, 3)
        assert recall == 0.5  # 2 out of 4 relevant docs

    def test_recall_at_k_all_retrieved(self):
        """Test Recall@K when all relevant are retrieved."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc2", "doc3"}

        recall = RetrievalMetrics.recall_at_k(retrieved, relevant, 3)
        assert recall == 1.0

    def test_f1_at_k(self):
        """Test F1@K calculation."""
        retrieved = ["doc1", "doc2", "doc3", "doc4"]
        relevant = {"doc1", "doc3", "doc5"}

        f1 = RetrievalMetrics.f1_at_k(retrieved, relevant, 4)
        # P = 0.5, R = 0.667, F1 = 2*0.5*0.667/(0.5+0.667) ≈ 0.571
        assert 0.5 <= f1 <= 0.7

    def test_mrr_first_hit(self):
        """Test MRR when first result is relevant."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1"}

        mrr = RetrievalMetrics.mrr(retrieved, relevant)
        assert mrr == 1.0

    def test_mrr_second_hit(self):
        """Test MRR when second result is relevant."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc2"}

        mrr = RetrievalMetrics.mrr(retrieved, relevant)
        assert mrr == 0.5

    def test_mrr_no_hit(self):
        """Test MRR when no relevant document is retrieved."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc4"}

        mrr = RetrievalMetrics.mrr(retrieved, relevant)
        assert mrr == 0.0

    def test_ndcg_at_k(self):
        """Test NDCG@K calculation."""
        retrieved = ["doc1", "doc2", "doc3", "doc4"]
        relevant = {"doc1", "doc3"}

        ndcg = RetrievalMetrics.ndcg_at_k(retrieved, relevant, 4)
        assert 0 < ndcg <= 1.0  # NDCG should be between 0 and 1

    def test_empty_relevant_set(self):
        """Test metrics with empty relevant set."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = set()

        recall = RetrievalMetrics.recall_at_k(retrieved, relevant, 3)
        assert recall == 0.0

    def test_average_precision(self):
        """Test Average Precision calculation."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3", "doc5"}

        ap = RetrievalMetrics.average_precision(retrieved, relevant)
        assert 0 < ap <= 1.0


class TestRAGEvaluator:
    """Tests for RAG system evaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create an evaluator."""
        return RAGEvaluator(k_values=[1, 3, 5])

    def test_evaluate_query(self, evaluator):
        """Test evaluating a single query."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3", "doc5"}

        result = evaluator.evaluate_query("test query", retrieved, relevant)

        assert isinstance(result, QueryEvaluation)
        assert result.query == "test query"
        assert 1 in result.precision_at_k
        assert 3 in result.recall_at_k
        assert 5 in result.ndcg_at_k

    def test_compute_average_metrics(self, evaluator):
        """Test computing average metrics."""
        # Evaluate multiple queries
        queries = [
            ("query1", ["doc1", "doc2"], {"doc1"}),
            ("query2", ["doc1", "doc2"], {"doc1", "doc2"}),
            ("query3", ["doc2", "doc3"], {"doc2"}),
        ]

        for query, retrieved, relevant in queries:
            evaluator.evaluate_query(query, retrieved, relevant)

        avg_metrics = evaluator.compute_average_metrics()

        assert "precision" in avg_metrics
        assert "recall" in avg_metrics
        assert "ndcg" in avg_metrics
        assert "mrr" in avg_metrics

    def test_generate_report(self, evaluator):
        """Test generating evaluation report."""
        evaluator.evaluate_query(
            "test query",
            ["doc1", "doc2", "doc3"],
            {"doc1", "doc2"}
        )

        report = evaluator.generate_report()
        assert report  # Should have content
        assert "Evaluation Report" in report


class TestGroundTruthDataset:
    """Tests for ground truth dataset."""

    @pytest.fixture
    def dataset(self):
        """Create a ground truth dataset."""
        return GroundTruthDataset()

    def test_get_relevant_documents_known_query(self, dataset):
        """Test getting relevant docs for known query."""
        relevant = dataset.get_relevant_documents("What are your working hours?")
        assert len(relevant) > 0
        assert any("Hours" in doc or "hours" in doc for doc in relevant)

    def test_get_relevant_documents_unknown_query(self, dataset):
        """Test getting relevant docs for unknown query."""
        relevant = dataset.get_relevant_documents("What is the meaning of life?")
        assert isinstance(relevant, set)

    def test_get_all_queries(self, dataset):
        """Test getting all test queries."""
        queries = dataset.get_all_queries()
        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)


class TestPerformanceMetrics:
    """Tests for performance metrics."""

    def test_empty_metrics(self):
        """Test metrics with no data."""
        metrics = PerformanceMetrics("test_operation")

        assert metrics.avg_latency == 0.0
        assert metrics.median_latency == 0.0
        assert metrics.p95_latency == 0.0
        assert metrics.throughput == 0.0

    def test_metrics_with_data(self):
        """Test metrics with latency data."""
        metrics = PerformanceMetrics("test_operation")
        metrics.total_calls = 10
        metrics.latencies = [0.1, 0.2, 0.15, 0.3, 0.25, 0.18, 0.22, 0.12, 0.28, 0.2]

        assert metrics.avg_latency > 0
        assert metrics.min_latency == 0.1
        assert metrics.max_latency == 0.3
        assert metrics.throughput > 0

    def test_percentiles(self):
        """Test percentile calculations."""
        metrics = PerformanceMetrics("test")
        metrics.total_calls = 100
        metrics.latencies = [i / 1000 for i in range(100)]  # 0 to 0.099

        # P95 should be higher than median
        assert metrics.p95_latency >= metrics.median_latency
        # P99 should be higher than P95
        assert metrics.p99_latency >= metrics.p95_latency

    def test_error_rate(self):
        """Test error rate calculation."""
        metrics = PerformanceMetrics("test")
        metrics.total_calls = 100
        metrics.errors = 5

        assert metrics.error_rate == 5.0

    def test_error_rate_no_errors(self):
        """Test error rate with no errors."""
        metrics = PerformanceMetrics("test")
        metrics.total_calls = 100
        metrics.errors = 0

        assert metrics.error_rate == 0.0


class TestPerformanceMonitor:
    """Tests for performance monitor."""

    @pytest.fixture
    def monitor(self):
        """Create a performance monitor."""
        return PerformanceMonitor()

    def test_record_latency(self, monitor):
        """Test recording latency."""
        monitor._record_latency("test_op", 0.5, error=False)

        metrics = monitor.get_metrics("test_op")
        assert metrics.total_calls == 1
        assert len(metrics.latencies) == 1

    def test_record_error(self, monitor):
        """Test recording error."""
        monitor._record_latency("test_op", 0.5, error=True)

        metrics = monitor.get_metrics("test_op")
        assert metrics.errors == 1
        assert len(metrics.latencies) == 0

    def test_get_metrics_nonexistent(self, monitor):
        """Test getting metrics for non-existent operation."""
        metrics = monitor.get_metrics("nonexistent")
        assert metrics.operation_name == "nonexistent"
        assert metrics.total_calls == 0

    def test_generate_report(self, monitor):
        """Test generating performance report."""
        monitor._record_latency("op1", 0.1, error=False)
        monitor._record_latency("op1", 0.2, error=False)
        monitor._record_latency("op2", 0.15, error=False)

        report = monitor.generate_report()
        assert report  # Should have content
        assert "Performance" in report or "op1" in report


class TestRAGPerformanceTest:
    """Tests for RAG performance testing."""

    @pytest.fixture
    def tester(self):
        """Create a performance tester."""
        return RAGPerformanceTest()

    def test_initialization(self, tester):
        """Test tester initialization."""
        assert tester.monitor is not None
        assert len(tester.test_queries) > 0

    def test_has_test_queries(self, tester):
        """Test that test queries exist."""
        assert any("hours" in q.lower() for q in tester.test_queries)
        assert any("price" in q.lower() or "cost" in q.lower() for q in tester.test_queries)
