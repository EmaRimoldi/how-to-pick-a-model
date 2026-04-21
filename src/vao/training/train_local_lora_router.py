"""Train a tiny local LoRA routing classifier without teacher/model calls."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import torch
import yaml
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from vao.logging_utils import read_jsonl, write_json
from vao.taxonomy import MODES
from vao.training.offline_routing_experiments import _prediction_row, summarize_prediction_rows
from vao.training.routing_features import DEFAULT_MAX_SOURCE_CHARS, record_to_text
from vao.training.train_routing_lora import split_records


def run_local_lora(config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("local_lora_router", config)
    seed = int(settings.get("seed", 5105))
    random.seed(seed)
    torch.manual_seed(seed)
    records = read_jsonl(Path(settings["dataset"]))
    train_records, eval_records = split_records(records, dev_fraction=float(settings.get("dev_fraction", 0.25)), seed=seed)
    model_id = str(settings.get("base_model", "distilbert-base-uncased"))
    max_source_chars = int(settings.get("max_source_chars", DEFAULT_MAX_SOURCE_CHARS))
    max_length = int(settings.get("max_length", 384))
    label_to_id = {mode: index for index, mode in enumerate(MODES)}
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id,
        num_labels=len(MODES),
        id2label={index: mode for mode, index in label_to_id.items()},
        label2id=label_to_id,
        local_files_only=True,
    )
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.SEQ_CLS,
            r=int(settings.get("lora_r", 4)),
            lora_alpha=int(settings.get("lora_alpha", 8)),
            lora_dropout=float(settings.get("lora_dropout", 0.0)),
            target_modules=list(settings.get("target_modules", ["q_lin", "v_lin"])),
        ),
    )
    optimizer = torch.optim.AdamW([param for param in model.parameters() if param.requires_grad], lr=float(settings.get("learning_rate", 3e-4)))
    batch_size = int(settings.get("batch_size", 2))
    epochs = int(settings.get("epochs", 3))
    losses = []
    model.train()
    for _ in range(epochs):
        shuffled = list(train_records)
        random.shuffle(shuffled)
        for start in range(0, len(shuffled), batch_size):
            batch = shuffled[start : start + batch_size]
            encoded = tokenizer(
                [record_to_text(record, max_source_chars=max_source_chars) for record in batch],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            labels = torch.tensor([label_to_id[str(record["productive_mode_top1"])] for record in batch], dtype=torch.long)
            optimizer.zero_grad()
            output = model(**encoded, labels=labels)
            output.loss.backward()
            optimizer.step()
            losses.append(float(output.loss.detach()))
    train_eval = evaluate_records(model, tokenizer, train_records, max_source_chars=max_source_chars, max_length=max_length)
    eval_eval = evaluate_records(model, tokenizer, eval_records, max_source_chars=max_source_chars, max_length=max_length)
    output_dir = Path(settings.get("output_dir", "training/offline_routing_student_lora"))
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir / "adapter")
    tokenizer.save_pretrained(output_dir / "tokenizer")
    summary = {
        "status": "completed",
        "base_model": model_id,
        "local_files_only": True,
        "record_count": len(records),
        "train_count": len(train_records),
        "eval_count": len(eval_records),
        "epochs": epochs,
        "batch_size": batch_size,
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "loss_decreased": (losses[-1] < losses[0]) if len(losses) >= 2 else None,
        "train_metrics": {key: value for key, value in train_eval.items() if key != "rows"},
        "eval_metrics": {key: value for key, value in eval_eval.items() if key != "rows"},
        "output_dir": str(output_dir),
    }
    write_json(Path(settings.get("summary_out", "artifacts/offline_lora_router_summary.json")), summary)
    write_json(Path(settings.get("predictions_out", "artifacts/offline_lora_router_predictions.json")), {"train": train_eval, "eval": eval_eval})
    return summary


def evaluate_records(model: torch.nn.Module, tokenizer: Any, records: list[dict[str, Any]], *, max_source_chars: int, max_length: int) -> dict[str, Any]:
    if not records:
        return summarize_prediction_rows("local_lora_router", [])
    model.eval()
    rows = []
    with torch.no_grad():
        for record in records:
            encoded = tokenizer(
                record_to_text(record, max_source_chars=max_source_chars),
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            logits = model(**encoded).logits[0]
            softmax = torch.softmax(logits, dim=-1)
            probs = {mode: float(softmax[index]) for index, mode in enumerate(MODES)}
            rows.append(_prediction_row(record, probs))
    return summarize_prediction_rows("local_lora_router", rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    summary = run_local_lora(config)
    print(json.dumps({"status": summary["status"], "eval_metrics": summary["eval_metrics"]}, indent=2, sort_keys=True, allow_nan=True))


if __name__ == "__main__":
    main()
