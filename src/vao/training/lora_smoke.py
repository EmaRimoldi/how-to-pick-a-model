"""Tiny local LoRA smoke test for routing-only training infrastructure."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model

from vao.logging_utils import write_json


class ToyRouter(torch.nn.Module):
    def __init__(self, input_dim: int = 8, output_dim: int = 6) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(input_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def run_smoke(steps: int = 40, seed: int = 5105) -> dict[str, Any]:
    torch.manual_seed(seed)
    x = torch.randn(24, 8)
    labels = (x[:, 0] + 0.5 * x[:, 1] > 0).long()
    labels = labels + ((x[:, 2] > 0).long() * 2)
    labels = labels.clamp(max=5)
    base = ToyRouter()
    model = get_peft_model(
        base,
        LoraConfig(
            r=2,
            lora_alpha=4,
            target_modules=["linear"],
            lora_dropout=0.0,
        ),
    )
    trainable_params = sum(param.numel() for param in model.parameters() if param.requires_grad)
    total_params = sum(param.numel() for param in model.parameters())
    optimizer = torch.optim.AdamW([param for param in model.parameters() if param.requires_grad], lr=0.05)
    loss_fn = torch.nn.CrossEntropyLoss()
    losses = []
    for _ in range(steps):
        optimizer.zero_grad()
        loss = loss_fn(model(x), labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    with torch.no_grad():
        accuracy = float((model(x).argmax(dim=1) == labels).float().mean())
    return {
        "status": "passed",
        "framework": "peft_lora_toy_linear",
        "steps": steps,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "loss_decreased": losses[-1] < losses[0],
        "train_accuracy": accuracy,
        "trainable_params": trainable_params,
        "total_params": total_params,
        "versions": package_versions(),
        "platform": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "install_commands": [
            "python -m pip install peft trl",
        ],
        "bitsandbytes_status": "not_installed; skipped because current platform is macOS arm64 and bitsandbytes is CUDA-oriented",
    }


def package_versions() -> dict[str, str]:
    versions = {}
    for name in ["torch", "transformers", "datasets", "accelerate", "peft", "trl", "bitsandbytes"]:
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "installed"))
        except Exception as exc:  # noqa: BLE001 - version audit should capture failures.
            versions[name] = f"unavailable:{type(exc).__name__}:{str(exc)[:160]}"
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "--version"], text=True, capture_output=True, check=False)
        versions["pip"] = proc.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        versions["pip"] = f"unavailable:{type(exc).__name__}"
    return versions


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/local_lora_smoke.json")
    parser.add_argument("--env_out", default="artifacts/local_training_stack_audit.json")
    parser.add_argument("--steps", type=int, default=40)
    args = parser.parse_args(argv)
    smoke = run_smoke(steps=args.steps)
    write_json(Path(args.out), smoke)
    write_json(
        Path(args.env_out),
        {
            "versions": smoke["versions"],
            "platform": smoke["platform"],
            "install_commands": smoke["install_commands"],
            "bitsandbytes_status": smoke["bitsandbytes_status"],
            "lora_smoke_out": args.out,
        },
    )
    print(json.dumps({"status": smoke["status"], "loss_decreased": smoke["loss_decreased"], "out": args.out}, indent=2))


if __name__ == "__main__":
    main()
