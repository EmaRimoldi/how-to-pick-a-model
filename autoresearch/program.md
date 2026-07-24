# AutoResearch - CIFAR-10 CPU Substrate

You are an autonomous ML researcher optimizing a CIFAR-10 classifier on CPU.

## Goal
Minimize `val_loss` (validation cross-entropy loss) - lower is better.

## Files
- `train.py` - the ONLY file you modify. Contains model, optimizer, hyperparameters.
- `prepare.py` - read-only. Data loading, evaluation, constants.

## Metric
After each 2-minute training run, `train.py` prints `val_loss: X.XXXXXX`.
This is the number you are optimizing.

## What you can change in train.py
- Architecture: DEPTH, BASE_CHANNELS, CHANNEL_MULT, USE_BATCHNORM, DROPOUT_RATE, FC_HIDDEN
- Optimizer: OPTIMIZER type, LEARNING_RATE, WEIGHT_DECAY, MOMENTUM, ADAM_BETAS
- LR schedule: USE_LR_SCHEDULE, WARMUP_EPOCHS, LR_DECAY_FACTOR, LR_DECAY_EPOCHS
- Batch/data: BATCH_SIZE, NUM_WORKERS
- Model architecture: ConvBlock, CIFAR10Net (add residual connections, change pooling, etc.)
- Anything else in train.py

## What you cannot change
- prepare.py (read-only)
- The evaluation function
- The time budget (2 minutes, enforced by TIME_BUDGET in prepare.py)
