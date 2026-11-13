"""Bounded graph and calibrated-text baselines for the private P4 study.

The graph construction follows the published WebGraphEval structure but uses a
deterministic, non-LLM canonicalizer.  The semantic baseline calibrates a small
CPU-only static embedding model on human STS Benchmark labels.  Neither lane is
an independent SOVA validation, and raw external text is never retained.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import platform
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT / "private" / "experiments" / "results" / "p4-graph-semantic-baselines-2026-08-01.json"
)
AGENTREWARD_RESULT = (
    ROOT / "private" / "experiments" / "results" / "agentreward-cross-model-study-2026-07-31.json"
)
AGENTREWARD_COMMIT = "271f96552e2e6dd13fe8e3572f0e5264039f6fd0"
MTEB_STSB_COMMIT = "96943a16ea6a35129e253c659081cb59daf81b30"
MODEL_COMMIT = "bf8b056651a2c21b8d2565580b8569da283cab23"
MODEL_ID = "minishlab/potion-base-8M"
MODEL2VEC_VERSION = "0.8.2"
GRAPH_MERGE_THRESHOLD = 0.9
GRAPH_EQUIVALENCE_THRESHOLD = 0.5
SEMANTIC_LABEL_THRESHOLD = 4.0
FORBIDDEN_RESULT_KEYS = {
    "action",
    "actions",
    "axtree",
    "chat_messages",
    "goal",
    "reasoning",
    "sentence1",
    "sentence2",
    "url",
}
WHITESPACE = re.compile(r"\s+")
VERB = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)")


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _directory_digest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    accumulator = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = child.relative_to(path).as_posix()
        raw = child.read_bytes()
        digest = _digest(raw)
        rows.append({"path": relative, "size": len(raw), "digest": digest})
        accumulator.update(relative.encode("utf-8"))
        accumulator.update(b"\0")
        accumulator.update(digest.encode("ascii"))
        accumulator.update(b"\n")
    return "sha256:" + accumulator.hexdigest(), rows


def _canonical_action(value: str) -> str:
    return WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).casefold().strip())


def _verb(value: str) -> str:
    match = VERB.match(value)
    return match.group(1).casefold() if match else "unknown"


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


@dataclass(frozen=True)
class GraphComparison:
    source_nodes: int
    candidate_nodes: int
    merged_nodes: int
    source_edges: int
    candidate_edges: int
    shared_edges: int
    node_jaccard: float
    edge_jaccard: float
    composite_similarity: float
    prediction: str


def _pair_graph(source: Sequence[str], candidate: Sequence[str]) -> GraphComparison:
    """Apply deterministic two-pass action merging and compare the two paths."""
    raw = list(source) + list(candidate)
    actions = [_canonical_action(item) for item in raw]
    verbs = [_verb(item) for item in raw]
    split = len(source)
    union = _UnionFind(len(actions))

    # Step-aligned pass, followed by same-verb cross-step merging.  WebGraphEval
    # uses the same two-pass topology but an LLM canonicalizer; this study does
    # not claim to reproduce that unavailable annotation component.
    for index in range(min(len(source), len(candidate))):
        left = index
        right = split + index
        if (
            verbs[left] == verbs[right]
            and SequenceMatcher(None, actions[left], actions[right], autojunk=False).ratio()
            >= GRAPH_MERGE_THRESHOLD
        ):
            union.union(left, right)
    for left in range(len(actions)):
        for right in range(left + 1, len(actions)):
            if verbs[left] != verbs[right]:
                continue
            if (
                SequenceMatcher(None, actions[left], actions[right], autojunk=False).ratio()
                >= GRAPH_MERGE_THRESHOLD
            ):
                union.union(left, right)

    source_path = [union.find(index) for index in range(split)]
    candidate_path = [union.find(index) for index in range(split, split + len(candidate))]
    source_nodes = set(source_path)
    candidate_nodes = set(candidate_path)
    source_edges = set(zip(source_path, source_path[1:]))
    candidate_edges = set(zip(candidate_path, candidate_path[1:]))

    node_union = source_nodes | candidate_nodes
    edge_union = source_edges | candidate_edges
    node_jaccard = len(source_nodes & candidate_nodes) / len(node_union) if node_union else 1.0
    edge_jaccard = len(source_edges & candidate_edges) / len(edge_union) if edge_union else 1.0
    composite = (node_jaccard + edge_jaccard) / 2
    return GraphComparison(
        source_nodes=len(source_nodes),
        candidate_nodes=len(candidate_nodes),
        merged_nodes=len(node_union),
        source_edges=len(source_edges),
        candidate_edges=len(candidate_edges),
        shared_edges=len(source_edges & candidate_edges),
        node_jaccard=node_jaccard,
        edge_jaccard=edge_jaccard,
        composite_similarity=composite,
        prediction=("equivalent" if composite >= GRAPH_EQUIVALENCE_THRESHOLD else "divergent"),
    )


def _jsonl_gzip(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"non-object row in {path.name}")
            rows.append(value)
    return rows


def _cosines(model: Any, rows: Sequence[dict[str, Any]]) -> np.ndarray[Any, Any]:
    left = [str(row["sentence1"]) for row in rows]
    right = [str(row["sentence2"]) for row in rows]
    left_vectors = np.asarray(model.encode(left), dtype=np.float64)
    right_vectors = np.asarray(model.encode(right), dtype=np.float64)
    numerator = np.sum(left_vectors * right_vectors, axis=1)
    denominator = np.linalg.norm(left_vectors, axis=1) * np.linalg.norm(right_vectors, axis=1)
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator != 0,
    )


def _sigmoid(value: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    clipped = np.clip(value, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _fit_platt(
    scores: np.ndarray[Any, Any], labels: np.ndarray[Any, Any]
) -> tuple[float, float, int]:
    design = np.column_stack((np.ones(len(scores)), scores))
    parameters = np.array([0.0, 1.0], dtype=np.float64)
    regularization = np.diag([0.0, 1e-3])
    for iteration in range(1, 101):
        probabilities = _sigmoid(design @ parameters)
        weights = np.clip(probabilities * (1.0 - probabilities), 1e-9, None)
        gradient = design.T @ (probabilities - labels) + regularization @ parameters
        hessian = design.T @ (weights[:, None] * design) + regularization
        update = np.linalg.solve(hessian, gradient)
        parameters -= update
        if float(np.max(np.abs(update))) < 1e-10:
            return float(parameters[0]), float(parameters[1]), iteration
    return float(parameters[0]), float(parameters[1]), 100


def _rank(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2 + 1
        start = end
    return ranks


def _correlation(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    if len(left) < 2 or float(np.std(left)) == 0 or float(np.std(right)) == 0:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _calibration_metrics(
    scores: np.ndarray[Any, Any],
    labels: np.ndarray[Any, Any],
    intercept: float,
    slope: float,
) -> dict[str, Any]:
    probabilities = _sigmoid(intercept + slope * scores)
    predictions = probabilities >= 0.5
    binary = labels.astype(bool)
    ece = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        mask = (probabilities >= lower) & (
            probabilities <= upper if upper >= 1.0 else probabilities < upper
        )
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(
                float(np.mean(probabilities[mask])) - float(np.mean(binary[mask]))
            )
    return {
        "count": len(scores),
        "positiveCount": int(np.sum(binary)),
        "accuracy": float(np.mean(predictions == binary)),
        "brier": float(np.mean((probabilities - labels) ** 2)),
        "ece10": ece,
        "probabilityMinimum": float(np.min(probabilities)),
        "probabilityMaximum": float(np.max(probabilities)),
    }


def _trajectory_vector(model: Any, actions: Sequence[str]) -> np.ndarray[Any, Any]:
    vectors = np.asarray(model.encode(list(actions)), dtype=np.float64)
    if vectors.ndim != 2 or len(vectors) == 0:
        raise RuntimeError("trajectory has no encodable actions")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms != 0)
    return np.mean(normalized, axis=0)


def _vector_cosine(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def _trajectory_files(root: Path) -> dict[tuple[str, str], Path]:
    files: dict[tuple[str, str], Path] = {}
    for path in root.glob("*.json"):
        source_path = path.name.replace("__", "/")
        segments = source_path.split("/")
        if len(segments) < 6:
            raise RuntimeError(f"unexpected flattened trajectory path: {path.name}")
        # The recorder's inner `model` field omits the agent-family prefix.  The
        # pinned external path is the identity used by the prior cohort study.
        model = segments[3]
        task_id = Path(source_path).stem
        files[(model, task_id)] = path
    if len(files) != 22:
        raise RuntimeError(f"expected 22 pinned trajectories, found {len(files)}")
    return files


def _actions(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    steps = document.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"trajectory lacks steps: {path.name}")
    actions = [
        str(step.get("action", "")).strip()
        for step in steps
        if isinstance(step, dict) and str(step.get("action", "")).strip()
    ]
    if not actions:
        raise RuntimeError(f"trajectory lacks observable actions: {path.name}")
    return actions


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_RESULT_KEYS for key in value) or any(
            _contains_forbidden_key(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _accuracy(rows: Iterable[dict[str, Any]], field: str) -> dict[str, Any]:
    conclusive = [row for row in rows if row["truth"] in {"equivalent", "divergent"}]
    correct = sum(row[field] == row["truth"] for row in conclusive)
    return {
        "correct": correct,
        "totalConclusive": len(conclusive),
        "accuracy": correct / len(conclusive) if conclusive else None,
        "multiValuedOutcomesSupported": False,
    }


def run(trajectory_root: Path, dataset_root: Path, model_root: Path) -> dict[str, Any]:
    from model2vec import StaticModel

    if importlib.metadata.version("model2vec") != MODEL2VEC_VERSION:
        raise RuntimeError("model2vec dependency drifted from the predeclared version")
    model = StaticModel.from_pretrained(str(model_root.resolve()))
    train_path = dataset_root / "train.jsonl.gz"
    validation_path = dataset_root / "validation.jsonl.gz"
    test_path = dataset_root / "test.jsonl.gz"
    dataset_paths = [train_path, validation_path, test_path]
    if not all(path.is_file() for path in dataset_paths):
        raise RuntimeError("the exact three STS Benchmark split files are required")

    started = perf_counter_ns()
    split_rows = {path.stem.split(".")[0]: _jsonl_gzip(path) for path in dataset_paths}
    split_scores = {name: _cosines(model, rows) for name, rows in split_rows.items()}
    split_labels = {
        name: np.asarray(
            [float(row["score"]) >= SEMANTIC_LABEL_THRESHOLD for row in rows],
            dtype=np.float64,
        )
        for name, rows in split_rows.items()
    }
    intercept, slope, iterations = _fit_platt(split_scores["train"], split_labels["train"])
    calibration = {
        name: {
            **_calibration_metrics(split_scores[name], split_labels[name], intercept, slope),
            "pearsonContinuous": _correlation(
                split_scores[name],
                np.asarray([float(row["score"]) / 5.0 for row in split_rows[name]]),
            ),
            "spearmanContinuous": _correlation(
                _rank(split_scores[name]),
                _rank(np.asarray([float(row["score"]) / 5.0 for row in split_rows[name]])),
            ),
        }
        for name in ("train", "validation", "test")
    }

    prior = json.loads(AGENTREWARD_RESULT.read_text(encoding="utf-8"))
    truth = {str(row["taskId"]): str(row["outcome"]) for row in prior["rows"]}
    models = sorted(prior["source"]["models"])
    if len(models) != 2:
        raise RuntimeError("expected two pinned AgentRewardBench model families")
    files = _trajectory_files(trajectory_root)
    rows: list[dict[str, Any]] = []
    source_model, candidate_model = models
    for task_id in sorted(truth):
        source_path = files[(source_model, task_id)]
        candidate_path = files[(candidate_model, task_id)]
        source_actions = _actions(source_path)
        candidate_actions = _actions(candidate_path)
        graph = _pair_graph(source_actions, candidate_actions)
        source_vector = _trajectory_vector(model, source_actions)
        candidate_vector = _trajectory_vector(model, candidate_actions)
        semantic_cosine = _vector_cosine(source_vector, candidate_vector)
        semantic_probability = float(_sigmoid(np.asarray(intercept + slope * semantic_cosine)))
        rows.append(
            {
                "taskId": task_id,
                "truth": truth[task_id],
                "sourceDigest": _file_digest(source_path),
                "candidateDigest": _file_digest(candidate_path),
                "sourceStepCount": len(source_actions),
                "candidateStepCount": len(candidate_actions),
                "graph": {
                    "sourceNodes": graph.source_nodes,
                    "candidateNodes": graph.candidate_nodes,
                    "mergedNodes": graph.merged_nodes,
                    "sourceEdges": graph.source_edges,
                    "candidateEdges": graph.candidate_edges,
                    "sharedEdges": graph.shared_edges,
                    "nodeJaccard": graph.node_jaccard,
                    "edgeJaccard": graph.edge_jaccard,
                    "compositeSimilarity": graph.composite_similarity,
                },
                "graphPrediction": graph.prediction,
                "semanticCosine": semantic_cosine,
                "semanticProbability": semantic_probability,
                "semanticPrediction": (
                    "equivalent" if semantic_probability >= 0.5 else "divergent"
                ),
            }
        )

    model_digest, model_files = _directory_digest(model_root)
    elapsed = perf_counter_ns() - started
    result: dict[str, Any] = {
        "artifactType": "sova.private-p4-graph-semantic-baselines",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "claimBoundary": (
            "Post-result same-team baseline study over pinned public trajectories and "
            "human STS labels. It is not blind calibration, independent validation, "
            "controlled re-execution, or a reproduction of WebGraphEval's LLM annotations."
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "model2vec": importlib.metadata.version("model2vec"),
            "numpy": importlib.metadata.version("numpy"),
            "workers": 1,
            "gpuUsed": False,
        },
        "sources": {
            "agentRewardBench": {
                "commit": AGENTREWARD_COMMIT,
                "trajectoryCount": len(files),
                "rawContentRetained": False,
                "licenseAsserted": False,
            },
            "webGraphEval": {
                "openReviewId": "IPpOtWGmdf",
                "methodBoundary": (
                    "two-pass deterministic edit-similarity action graph; no LLM "
                    "canonicalization, necessity labels, or claimed code integration"
                ),
                "mergeThreshold": GRAPH_MERGE_THRESHOLD,
                "postResultEquivalenceThreshold": GRAPH_EQUIVALENCE_THRESHOLD,
            },
            "stsBenchmark": {
                "mtebCommit": MTEB_STSB_COMMIT,
                "license": "unknown; private evaluation only; no redistribution",
                "splits": [
                    {
                        "name": path.stem.split(".")[0],
                        "rows": len(split_rows[path.stem.split(".")[0]]),
                        "size": path.stat().st_size,
                        "digest": _file_digest(path),
                    }
                    for path in dataset_paths
                ],
                "binaryLabelRule": f"human score >= {SEMANTIC_LABEL_THRESHOLD}",
            },
            "semanticModel": {
                "id": MODEL_ID,
                "commit": MODEL_COMMIT,
                "model2vecWheelSha256": (
                    "f0ecfe994316e401dca583fbf6dd22079d308c05717dd36d40bff60f265431cf"
                ),
                "license": "MIT",
                "directoryDigest": model_digest,
                "files": model_files,
            },
        },
        "calibration": {
            "method": "Platt logistic calibration on train cosine; no test refit",
            "intercept": intercept,
            "slope": slope,
            "iterations": iterations,
            "splits": calibration,
        },
        "trajectoryRows": rows,
        "trajectoryMetrics": {
            "graph": _accuracy(rows, "graphPrediction"),
            "semantic": _accuracy(rows, "semanticPrediction"),
        },
        "performance": {
            "totalNanoseconds": elapsed,
            "stsPairs": sum(len(items) for items in split_rows.values()),
            "trajectoryPairs": len(rows),
            "sourceBytes": sum(path.stat().st_size for path in dataset_paths)
            + sum(path.stat().st_size for path in files.values()),
        },
        "privacy": {
            "rawSentencesRetained": False,
            "rawActionsRetained": False,
            "goalsUrlsReasoningRetained": False,
            "knownForbiddenResultKeyCount": 0,
        },
        "limitations": [
            "The graph adaptation is same-team and post-result; its threshold is exploratory.",
            "Only two trajectories exist per task, far below WebGraphEval's intended corpus scale.",
            "The deterministic canonicalizer is not WebGraphEval's LLM canonicalizer.",
            "STS calibration is out of domain for web-action sequences and does not validate SOVA labels.",
            "Embedding probability cannot represent incompatible, inconclusive, unsafe, or invalid evidence.",
            "Dataset licensing is not asserted, so source content is not redistributed.",
        ],
    }
    if _contains_forbidden_key(result):
        raise RuntimeError("forbidden raw-content key leaked into retained result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.trajectory_root, args.dataset_root, args.model_root)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
