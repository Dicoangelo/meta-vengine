#!/usr/bin/env python3
"""pca.py — Pure Python PCA for projecting cluster centroids to 2D.

No numpy dependency. Uses power iteration to find top-2 eigenvectors
of the covariance matrix, then projects N-dim centroids to 2D.
"""

import math
from typing import List, Tuple


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _scale(v: List[float], s: float) -> List[float]:
    return [x * s for x in v]


def _subtract(a: List[float], b: List[float]) -> List[float]:
    return [x - y for x, y in zip(a, b)]


def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: List[float]) -> List[float]:
    n = _norm(v)
    if n < 1e-12:
        return v
    return [x / n for x in v]


def _mat_vec(mat: List[List[float]], v: List[float]) -> List[float]:
    """Multiply matrix (list of rows) by vector."""
    return [_dot(row, v) for row in mat]


def _covariance_matrix(centered: List[List[float]], dim: int) -> List[List[float]]:
    """Compute covariance matrix from mean-centered data."""
    n = len(centered)
    if n <= 1:
        return [[0.0] * dim for _ in range(dim)]
    cov = [[0.0] * dim for _ in range(dim)]
    for row in centered:
        for i in range(dim):
            for j in range(i, dim):
                val = row[i] * row[j]
                cov[i][j] += val
                if i != j:
                    cov[j][i] += val
    factor = 1.0 / (n - 1) if n > 1 else 1.0
    for i in range(dim):
        for j in range(dim):
            cov[i][j] *= factor
    return cov


def _power_iteration(
    mat: List[List[float]], dim: int, iterations: int = 100
) -> List[float]:
    """Find dominant eigenvector via power iteration."""
    # Start with a vector that has all components nonzero
    v = [1.0 / math.sqrt(dim)] * dim
    # Add slight perturbation to break symmetry
    for i in range(dim):
        v[i] += (i + 1) * 0.01
    v = _normalize(v)

    for _ in range(iterations):
        v_new = _mat_vec(mat, v)
        v_new = _normalize(v_new)
        if v_new == v:
            break
        v = v_new
    return v


def _deflate(
    mat: List[List[float]], eigenvector: List[float], dim: int
) -> List[List[float]]:
    """Remove component of dominant eigenvector from covariance matrix (deflation)."""
    eigenvalue = _dot(_mat_vec(mat, eigenvector), eigenvector)
    deflated = [row[:] for row in mat]
    for i in range(dim):
        for j in range(dim):
            deflated[i][j] -= eigenvalue * eigenvector[i] * eigenvector[j]
    return deflated


def project_to_2d(vectors: List[List[float]]) -> List[Tuple[float, float]]:
    """Project N-dimensional vectors to 2D using PCA.

    Args:
        vectors: list of N-dim vectors (centroids)

    Returns:
        list of (x, y) tuples — 2D projected points

    Edge cases:
        - 0 vectors: returns []
        - 1 vector: returns [(0.0, 0.0)]
        - <2 dims: returns raw first 2 dims (or 0-padded)
    """
    if not vectors:
        return []

    n = len(vectors)
    if n == 1:
        return [(0.0, 0.0)]

    dim = len(vectors[0])

    # If vectors are less than 2D, return raw values
    if dim < 2:
        return [(v[0] if len(v) > 0 else 0.0, 0.0) for v in vectors]

    if dim == 2:
        return [(v[0], v[1]) for v in vectors]

    # Center data (subtract mean)
    mean = [sum(v[i] for v in vectors) / n for i in range(dim)]
    centered = [_subtract(v, mean) for v in vectors]

    # Compute covariance matrix
    cov = _covariance_matrix(centered, dim)

    # Power iteration for first eigenvector
    ev1 = _power_iteration(cov, dim, iterations=100)

    # Deflation: remove first component
    cov_deflated = _deflate(cov, ev1, dim)

    # Power iteration for second eigenvector
    ev2 = _power_iteration(cov_deflated, dim, iterations=100)

    # Project each centered vector onto the 2 eigenvectors
    result = []
    for c in centered:
        x = _dot(c, ev1)
        y = _dot(c, ev2)
        result.append((round(x, 6), round(y, 6)))

    return result
