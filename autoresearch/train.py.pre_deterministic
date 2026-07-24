"""CIFAR-10 training script - the agent modifies this file.

Metric: val_loss (cross-entropy on validation set, lower is better).
Time budget: 2 minutes wall-clock for training.
Device: CPU only.
"""

from __future__ import annotations

import time

import torch
import torch.nn as nn
import torch.optim as optim

from prepare import (
    EVAL_BATCH_SIZE,
    IMAGE_SIZE,
    INPUT_CHANNELS,
    NUM_CLASSES,
    TIME_BUDGET,
    evaluate_accuracy,
    evaluate_loss,
    get_train_loader,
)


# --- Architecture hyperparameters -------------------------------------------
DEPTH = 3
BASE_CHANNELS = 32
CHANNEL_MULT = 2
USE_BATCHNORM = True
DROPOUT_RATE = 0.0
FC_HIDDEN = 128

# --- Optimizer hyperparameters ----------------------------------------------
OPTIMIZER = "adam"
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
MOMENTUM = 0.9
ADAM_BETAS = (0.9, 0.999)

# --- LR schedule hyperparameters --------------------------------------------
USE_LR_SCHEDULE = True
WARMUP_EPOCHS = 2
LR_DECAY_FACTOR = 0.1
LR_DECAY_EPOCHS = [60, 80]

# --- Batch / data hyperparameters -------------------------------------------
BATCH_SIZE = 128
NUM_WORKERS = 2


class ConvBlock(nn.Module):
    """Conv -> optional BN -> ReLU -> optional Dropout."""

    def __init__(self, in_ch, out_ch, use_bn=True, dropout=0.0):
        super().__init__()
        layers = [nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=not use_bn)]
        if use_bn:
            layers.append(nn.BatchNorm2d(out_ch))
        layers.append(nn.ReLU(inplace=True))
        if dropout > 0:
            layers.append(nn.Dropout2d(dropout))
        layers.append(nn.MaxPool2d(2))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)


class CIFAR10Net(nn.Module):
    """Simple CNN for CIFAR-10 classification."""

    def __init__(self):
        super().__init__()
        layers = []
        in_ch = INPUT_CHANNELS
        out_ch = BASE_CHANNELS
        for _ in range(DEPTH):
            layers.append(ConvBlock(in_ch, out_ch, USE_BATCHNORM, DROPOUT_RATE))
            in_ch = out_ch
            out_ch = min(out_ch * CHANNEL_MULT, 512)

        self.features = nn.Sequential(*layers)

        feat_size = IMAGE_SIZE // (2**DEPTH)
        feat_dim = in_ch * feat_size * feat_size

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(feat_dim, FC_HIDDEN),
            nn.ReLU(inplace=True),
            nn.Dropout(DROPOUT_RATE),
            nn.Linear(FC_HIDDEN, NUM_CLASSES),
        )

    def forward(self, x):
        x = self.features(x)
        return self.classifier(x)


def build_optimizer(model):
    if OPTIMIZER == "adam":
        return optim.Adam(
            model.parameters(),
            lr=LEARNING_RATE,
            betas=ADAM_BETAS,
            weight_decay=WEIGHT_DECAY,
        )
    if OPTIMIZER == "adamw":
        return optim.AdamW(
            model.parameters(),
            lr=LEARNING_RATE,
            betas=ADAM_BETAS,
            weight_decay=WEIGHT_DECAY,
        )
    if OPTIMIZER == "sgd":
        return optim.SGD(
            model.parameters(),
            lr=LEARNING_RATE,
            momentum=MOMENTUM,
            weight_decay=WEIGHT_DECAY,
        )
    raise ValueError(f"Unknown optimizer: {OPTIMIZER}")


def build_scheduler(optimizer, steps_per_epoch):
    if not USE_LR_SCHEDULE:
        return None
    total_steps = steps_per_epoch * 100
    return optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)


def main():
    device = "cpu"
    t_start = time.time()

    seed = int(time.time() * 1000) % (2**32)
    torch.manual_seed(seed)

    train_loader = get_train_loader(BATCH_SIZE, NUM_WORKERS)
    steps_per_epoch = len(train_loader)

    model = CIFAR10Net().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model)
    scheduler = build_scheduler(optimizer, steps_per_epoch)

    total_training_time = 0.0
    step = 0
    epoch = 0

    while True:
        model.train()
        epoch += 1
        for images, labels in train_loader:
            step_start = time.time()
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            if scheduler is not None:
                scheduler.step()

            step += 1
            dt = time.time() - step_start
            total_training_time += dt

            if total_training_time >= TIME_BUDGET:
                break

            if torch.isnan(loss):
                print("ERROR: NaN loss detected, aborting.")
                print("---")
                print("val_loss:          nan")
                print("val_bpb:           nan")
                print("val_accuracy:      0.0")
                print(f"training_seconds:  {total_training_time:.1f}")
                print(f"total_seconds:     {time.time() - t_start:.1f}")
                return

        if total_training_time >= TIME_BUDGET:
            break

    val_loss = evaluate_loss(model, device)
    val_acc = evaluate_accuracy(model, device)
    t_end = time.time()

    param_count = sum(p.numel() for p in model.parameters())

    print("---")
    print(f"val_loss:          {val_loss:.6f}")
    print(f"val_bpb:           {val_loss:.6f}")
    print(f"val_accuracy:      {val_acc:.4f}")
    print(f"training_seconds:  {total_training_time:.1f}")
    print(f"total_seconds:     {t_end - t_start:.1f}")
    print(f"total_steps:       {step}")
    print(f"total_epochs:      {epoch}")
    print(f"param_count:       {param_count}")


if __name__ == "__main__":
    main()
