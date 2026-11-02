"""Chains of cubic Bezier segments: sampling, and nodes with tangents for fitting."""
import numpy as np


def to_nodes(segments):
    """Chain -> nodes [(point, unit tangent, handle in, handle out)]."""
    nodes = []
    for i in range(len(segments) + 1):
        p = np.array(segments[i][0] if i < len(segments) else segments[-1][3], float)
        h_in = p - np.array(segments[i - 1][2], float) if i else None
        h_out = np.array(segments[i][1], float) - p if i < len(segments) else None
        t = h_out if h_out is not None else h_in
        t = t / np.linalg.norm(t)
        nodes.append([p, t, np.linalg.norm(h_in) if i else 0.0, np.linalg.norm(h_out) if h_out is not None else 0.0])
    return nodes


def to_segments(nodes):
    return [[n0[0], n0[0] + n0[3] * n0[1], n1[0] - n1[2] * n1[1], n1[0]] for n0, n1 in zip(nodes, nodes[1:])]


def sample(segments, n=60):
    t = np.linspace(0, 1, n)[:, None]
    return np.vstack([(1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
                      for a, b, c, d in (map(np.asarray, s) for s in segments)])
