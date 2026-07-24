"""Render clean AutoResearch substrate architecture diagrams.

The diagrams are presentation assets for the README. They intentionally avoid a
framework-specific visualizer so they can be regenerated with the base plotting
dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "assets" / "autoresearch"


@dataclass(frozen=True)
class Stage:
    title: str
    detail: str
    color: str


@dataclass(frozen=True)
class Substrate:
    slug: str
    title: str
    subtitle: str
    stages: tuple[Stage, ...]
    note: str


SUBSTRATES = (
    Substrate(
        slug="mlp",
        title="MLP Flat",
        subtitle="3 x 32 x 32 image flattened into dense layers",
        stages=(
            Stage("Input", "CIFAR-10\n3 x 32 x 32", "#111827"),
            Stage("Flatten", "3072 features", "#0f766e"),
            Stage("Dense 1", "Linear 3072 -> 192\nBatchNorm + GELU", "#2563eb"),
            Stage("Dense 2", "Linear 192 -> 384\nBatchNorm + GELU", "#7c3aed"),
            Stage("Classifier", "Linear 384 -> 10\nclass logits", "#ea580c"),
        ),
        note="Approx. 669k trainable parameters. Useful for testing pure hyperparameter and representation edits.",
    ),
    Substrate(
        slug="compact-cnn",
        title="Compact CNN",
        subtitle="Two convolutional stages followed by a small classifier",
        stages=(
            Stage("Input", "CIFAR-10\n3 x 32 x 32", "#111827"),
            Stage("Conv Block 1", "3 -> 12 channels\n3 x 3 + BN + ReLU\nMaxPool", "#0f766e"),
            Stage("Conv Block 2", "12 -> 24 channels\n3 x 3 + BN + ReLU\nMaxPool", "#2563eb"),
            Stage("Dense", "1536 -> 48\nReLU", "#7c3aed"),
            Stage("Classifier", "48 -> 10\nclass logits", "#ea580c"),
        ),
        note="Approx. 77k trainable parameters. A small vision model where local image features matter.",
    ),
    Substrate(
        slug="micro-resnet",
        title="Micro ResNet",
        subtitle="Tiny residual network with global average pooling",
        stages=(
            Stage("Input", "CIFAR-10\n3 x 32 x 32", "#111827"),
            Stage("Stem", "3 -> 8 channels\n3 x 3 + BN + ReLU", "#0f766e"),
            Stage("Residual Path", "Conv + BN + ReLU\nskip connection\nConv + BN", "#2563eb"),
            Stage("Pool", "global average\n8 features", "#7c3aed"),
            Stage("Classifier", "8 -> 32 -> 10\nclass logits", "#ea580c"),
        ),
        note="Approx. 2.6k trainable parameters. A deliberately tiny residual substrate for architecture-sensitive edits.",
    ),
)


def add_box(ax: plt.Axes, x: float, y: float, w: float, h: float, stage: Stage) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.035",
        linewidth=1.8,
        edgecolor=stage.color,
        facecolor="#ffffff",
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h * 0.62,
        stage.title,
        ha="center",
        va="center",
        fontsize=15,
        fontweight="bold",
        color=stage.color,
    )
    ax.text(
        x + w / 2,
        y + h * 0.34,
        stage.detail,
        ha="center",
        va="center",
        fontsize=10.5,
        color="#111827",
        linespacing=1.2,
    )


def draw(substrate: Substrate) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 6.2), dpi=220)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.035, 0.93, substrate.title, fontsize=25, fontweight="bold", color="#0f172a", va="top")
    ax.text(0.035, 0.865, substrate.subtitle, fontsize=13.5, color="#334155", va="top")

    n = len(substrate.stages)
    left, right = 0.04, 0.96
    gap = 0.038
    w = (right - left - gap * (n - 1)) / n
    y, h = 0.39, 0.29
    centers = []
    for idx, stage in enumerate(substrate.stages):
        x = left + idx * (w + gap)
        add_box(ax, x, y, w, h, stage)
        centers.append((x + w / 2, stage.color))

    for idx in range(n - 1):
        x0 = left + idx * (w + gap) + w + 0.004
        x1 = left + (idx + 1) * (w + gap) - 0.004
        ymid = y + h / 2
        ax.annotate(
            "",
            xy=(x1, ymid),
            xytext=(x0, ymid),
            arrowprops=dict(arrowstyle="-|>", lw=1.8, color="#475569", shrinkA=0, shrinkB=0),
            zorder=2,
        )

    ax.plot([0.035, 0.965], [0.25, 0.25], color="#cbd5e1", lw=1.2)
    ax.text(
        0.035,
        0.19,
        substrate.note,
        fontsize=12,
        color="#334155",
        va="center",
        ha="left",
    )
    ax.text(
        0.965,
        0.08,
        "AutoResearch CIFAR-10 substrate",
        fontsize=10.5,
        color="#64748b",
        ha="right",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        fig.savefig(OUT_DIR / f"neural-substrate-{substrate.slug}.{suffix}", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)


def main() -> None:
    for substrate in SUBSTRATES:
        draw(substrate)


if __name__ == "__main__":
    main()
