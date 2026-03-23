"""Evaluation metrics for RAG system performance."""

import time
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

import numpy as np


@dataclass
class QueryEvaluation:
    """Result of evaluating a single query."""
    query: str
    retrieved_docs: List[str]
    relevant_docs: Set[str]
    precision_at_k: Dict[int, float]
    recall_at_k: Dict[int, float]
    ndcg_at_k: Dict[int, float]
    mrr: float


class RetrievalMetrics:
    """Calculate retrieval quality metrics."""

    @staticmethod
    def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Calculate Precision@K.

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs
            k: Number of top results to consider

        Returns:
            Precision@K score
        """
        if k == 0:
            return 0.0

        top_k = retrieved[:k]
        relevant_retrieved = sum(1 for doc in top_k if doc in relevant)
        return relevant_retrieved / k

    @staticmethod
    def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Calculate Recall@K.

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs
            k: Number of top results to consider

        Returns:
            Recall@K score
        """
        if not relevant:
            return 0.0

        top_k = retrieved[:k]
        relevant_retrieved = sum(1 for doc in top_k if doc in relevant)
        return relevant_retrieved / len(relevant)

    @staticmethod
    def f1_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Calculate F1@K.

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs
            k: Number of top results to consider

        Returns:
            F1@K score
        """
        precision = RetrievalMetrics.precision_at_k(retrieved, relevant, k)
        recall = RetrievalMetrics.recall_at_k(retrieved, relevant, k)

        if precision + recall == 0:
            return 0.0

        return 2 * (precision * recall) / (precision + recall)

    @staticmethod
    def average_precision(retrieved: List[str], relevant: Set[str]) -> float:
        """
        Calculate Average Precision.

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs

        Returns:
            Average Precision score
        """
        if not relevant:
            return 0.0

        precisions = []
        relevant_found = 0

        for i, doc in enumerate(retrieved, 1):
            if doc in relevant:
                relevant_found += 1
                precisions.append(relevant_found / i)

        return sum(precisions) / len(relevant) if precisions else 0.0

    @staticmethod
    def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
        """
        Calculate NDCG@K (Normalized Discounted Cumulative Gain).

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs (binary relevance)
            k: Number of top results to consider

        Returns:
            NDCG@K score
        """
        def dcg_at_k(relevances: List[int], k: int) -> float:
            """Calculate DCG@K."""
            return sum((rel / np.log2(i + 2)) for i, rel in enumerate(relevances[:k]))

        # Binary relevance: 1 if relevant, 0 otherwise
        relevances = [1 if doc in relevant else 0 for doc in retrieved[:k]]

        # DCG
        dcg = dcg_at_k(relevances, k)

        # Ideal DCG (all relevant documents at top)
        ideal_relevances = sorted(relevances, reverse=True)
        idcg = dcg_at_k(ideal_relevances, k)

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def mrr(retrieved: List[str], relevant: Set[str]) -> float:
        """
        Calculate Mean Reciprocal Rank.

        Args:
            retrieved: List of retrieved document IDs
            relevant: Set of relevant document IDs

        Returns:
            MRR score
        """
        for i, doc in enumerate(retrieved, 1):
            if doc in relevant:
                return 1.0 / i
        return 0.0


class RAGEvaluator:
    """Evaluate RAG system performance."""

    def __init__(self, k_values: List[int] = None):
        """Initialize evaluator."""
        self.k_values = k_values or [1, 3, 5, 10]
        self.evaluations: List[QueryEvaluation] = []

    def evaluate_query(
        self,
        query: str,
        retrieved_docs: List[str],
        relevant_docs: Set[str],
    ) -> QueryEvaluation:
        """
        Evaluate a single query.

        Args:
            query: The search query
            retrieved_docs: List of retrieved document IDs
            relevant_docs: Set of relevant document IDs

        Returns:
            QueryEvaluation with metrics
        """
        precision_at_k = {}
        recall_at_k = {}
        ndcg_at_k = {}

        for k in self.k_values:
            precision_at_k[k] = RetrievalMetrics.precision_at_k(
                retrieved_docs, relevant_docs, k
            )
            recall_at_k[k] = RetrievalMetrics.recall_at_k(
                retrieved_docs, relevant_docs, k
            )
            ndcg_at_k[k] = RetrievalMetrics.ndcg_at_k(
                retrieved_docs, relevant_docs, k
            )

        mrr = RetrievalMetrics.mrr(retrieved_docs, relevant_docs)

        evaluation = QueryEvaluation(
            query=query,
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs,
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            ndcg_at_k=ndcg_at_k,
            mrr=mrr,
        )

        self.evaluations.append(evaluation)
        return evaluation

    def compute_average_metrics(self) -> Dict[str, Dict[int, float]]:
        """
        Compute average metrics across all evaluations.

        Returns:
            Dict with averaged precision, recall, NDCG at each K
        """
        if not self.evaluations:
            return {}

        avg_metrics = {
            "precision": {k: 0.0 for k in self.k_values},
            "recall": {k: 0.0 for k in self.k_values},
            "ndcg": {k: 0.0 for k in self.k_values},
            "f1": {k: 0.0 for k in self.k_values},
            "mrr": 0.0,
        }

        for eval in self.evaluations:
            for k in self.k_values:
                avg_metrics["precision"][k] += eval.precision_at_k[k]
                avg_metrics["recall"][k] += eval.recall_at_k[k]
                avg_metrics["ndcg"][k] += eval.ndcg_at_k[k]
            avg_metrics["mrr"] += eval.mrr

        # Divide by number of evaluations
        n = len(self.evaluations)
        for k in self.k_values:
            avg_metrics["precision"][k] /= n
            avg_metrics["recall"][k] /= n
            avg_metrics["ndcg"][k] /= n
            # Compute F1 from averages
            p = avg_metrics["precision"][k]
            r = avg_metrics["recall"][k]
            avg_metrics["f1"][k] = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        avg_metrics["mrr"] /= n

        return avg_metrics

    def generate_report(self) -> str:
        """Generate a text report of evaluation results."""
        if not self.evaluations:
            return "No evaluations to report."

        metrics = self.compute_average_metrics()

        lines = [
            "=" * 60,
            "RAG System Evaluation Report",
            "=" * 60,
            f"Total Queries Evaluated: {len(self.evaluations)}",
            "",
            "Retrieval Metrics:",
            "-" * 40,
        ]

        for k in self.k_values:
            lines.extend([
                f"K={k}:",
                f"  Precision@{k}: {metrics['precision'][k]:.4f}",
                f"  Recall@{k}: {metrics['recall'][k]:.4f}",
                f"  F1@{k}: {metrics['f1'][k]:.4f}",
                f"  NDCG@{k}: {metrics['ndcg'][k]:.4f}",
                "",
            ])

        lines.extend([
            f"Mean Reciprocal Rank (MRR): {metrics['mrr']:.4f}",
            "",
        ])

        return "\n".join(lines)


class GroundTruthDataset:
    """Ground truth dataset for evaluation."""

    def __init__(self):
        """Initialize ground truth dataset."""
        self.queries: Dict[str, Set[str]] = {}

        # Parking-specific test queries
        self._load_parking_queries()

    def _load_parking_queries(self) -> None:
        """Load parking-specific test queries."""
        self.queries = {
            "What are your working hours?": {"Working Hours"},
            "How much does it cost to park?": {"Pricing"},
            "Where is the parking located?": {"Location"},
            "How do I make a reservation?": {"Booking and Reservation Process"},
            "What types of parking spaces are available?": {"Parking Space Types"},
            "What payment methods do you accept?": {"Payment Options"},
            "What are the parking rules?": {"Rules and Regulations"},
            "Is there EV charging available?": {"EV Charging Station Rules", "Facility Features"},
            "Are there accessible parking spaces?": {"Accessibility"},
            "What is the maximum daily rate?": {"Pricing"},
        }

    def get_relevant_documents(self, query: str) -> Set[str]:
        """Get relevant documents for a query."""
        # Try exact match
        if query in self.queries:
            return self.queries[query]

        # Try fuzzy match
        query_lower = query.lower()
        for test_query, docs in self.queries.items():
            if query_lower in test_query.lower() or test_query.lower() in query_lower:
                return docs

        return set()

    def get_all_queries(self) -> List[str]:
        """Get all test queries."""
        return list(self.queries.keys())


def evaluate_rag_system() -> str:
    """
    Run a comprehensive RAG system evaluation.

    Returns:
        Evaluation report as string.
    """
    from src.core.rag_engine import get_rag_engine
    from src.core.vector_store import get_vector_store

    # Initialize components
    rag_engine = get_rag_engine(use_mock=True)
    vector_store = get_vector_store(use_in_memory=True)

    # Initialize vector store if needed
    info = vector_store.get_collection_info()
    if info.get("num_entities", 0) == 0:
        from src.core.vector_store import initialize_vector_store
        initialize_vector_store()

    # Create evaluator
    evaluator = RAGEvaluator(k_values=[1, 3, 5])
    ground_truth = GroundTruthDataset()

    # Evaluate each query
    for query in ground_truth.get_all_queries():
        # Get retrieved documents
        results = vector_store.search(query, top_k=5)

        # Extract document IDs/sections
        retrieved = []
        for result in results:
            metadata = result.get("metadata", "{}")
            # Extract section from metadata
            if "section" in metadata:
                retrieved.append(metadata.split("'section': '")[1].split("'")[0])
            else:
                retrieved.append(f"doc_{result.get('document_id', 'unknown')}")

        # Get relevant documents
        relevant = ground_truth.get_relevant_documents(query)

        # Evaluate
        evaluator.evaluate_query(query, retrieved, relevant)

    # Generate and return report
    return evaluator.generate_report()


if __name__ == "__main__":
    # Run evaluation when executed directly
    print(evaluate_rag_system())
