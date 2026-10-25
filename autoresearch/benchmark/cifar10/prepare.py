"""Fixed constants, data download, and evaluation harness.
DO NOT MODIFY - this is read-only for the agent.
"""

from __future__ import annotations

import os
import pickle
import random
import tarfile
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# --- Determinism preamble (module-level) ------------------------------------
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)
os.environ["PYTHONHASHSEED"] = "42"
torch.set_num_threads(1)
torch.set_num_interop_threads(1)

try:
    from PIL import Image
    from torchvision import datasets, transforms  # type: ignore
except ModuleNotFoundError:
    datasets = None
    transforms = None
    Image = None


# --- Constants ---------------------------------------------------------------
TIME_BUDGET = 120
EVAL_BATCH_SIZE = 256
NUM_CLASSES = 10
INPUT_CHANNELS = 3
IMAGE_SIZE = 32
DATA_DIR = os.environ.get("AUTOSEARCH_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DEFAULT_DATA_SEED = 42
DEFAULT_TRAIN_SUBSET = 50000
DEFAULT_VAL_SUBSET = 10000
DEFAULT_LABEL_NOISE = 0.0
DEFAULT_IMBALANCE_RATIO = 1.0

_CIFAR_URL = "https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"
_CIFAR_ARCHIVE = "cifar-10-python.tar.gz"
_CIFAR_DIRNAME = "cifar-10-batches-py"


if transforms is not None:
    _transform_train = transforms.Compose(
        [
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(
                (0.4914, 0.4822, 0.4465),
                (0.2470, 0.2435, 0.2616),
            ),
        ]
    )

    _transform_val = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                (0.4914, 0.4822, 0.4465),
                (0.2470, 0.2435, 0.2616),
            ),
        ]
    )
else:
    class Compose:
        def __init__(self, transforms_list: list):
            self.transforms = transforms_list

        def __call__(self, image):
            for transform in self.transforms:
                image = transform(image)
            return image


    class RandomCrop:
        def __init__(self, size: int, padding: int = 0):
            self.size = size
            self.padding = padding

        def __call__(self, image):
            if self.padding > 0:
                image = torch.nn.functional.pad(
                    image, (self.padding, self.padding, self.padding, self.padding)
                )
            _, height, width = image.shape
            top = torch.randint(0, height - self.size + 1, (1,)).item()
            left = torch.randint(0, width - self.size + 1, (1,)).item()
            return image[:, top : top + self.size, left : left + self.size]


    class RandomHorizontalFlip:
        def __init__(self, p: float = 0.5):
            self.p = p

        def __call__(self, image):
            if torch.rand(1).item() < self.p:
                return torch.flip(image, dims=(2,))
            return image


    class ToTensor:
        def __call__(self, image):
            if isinstance(image, torch.Tensor):
                return image
            array = np.asarray(image, dtype=np.float32)
            return torch.from_numpy(array).permute(2, 0, 1) / 255.0


    class Normalize:
        def __init__(self, mean: tuple[float, ...], std: tuple[float, ...]):
            self.mean = torch.tensor(mean, dtype=torch.float32).view(-1, 1, 1)
            self.std = torch.tensor(std, dtype=torch.float32).view(-1, 1, 1)

        def __call__(self, image):
            return (image - self.mean) / self.std


    class CIFAR10Dataset(Dataset):
        def __init__(self, root: str | Path, train: bool, transform=None):
            self.root = Path(root)
            self.train = train
            self.transform = transform
            _ensure_cifar_downloaded(self.root)
            self.data, self.targets = _load_cifar_split(self.root, train=train)

        def __len__(self) -> int:
            return len(self.targets)

        def __getitem__(self, index: int):
            image = torch.from_numpy(self.data[index]).float().div(255.0)
            label = int(self.targets[index])
            if self.transform is not None:
                image = self.transform(image)
            return image, label


    _transform_train = Compose(
        [
            RandomCrop(32, padding=4),
            RandomHorizontalFlip(),
            Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
        ]
    )

    _transform_val = Compose(
        [
            Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
        ]
    )


def _ensure_cifar_downloaded(root: str | Path) -> None:
    root_path = Path(root)
    batch_dir = root_path / _CIFAR_DIRNAME
    if batch_dir.exists():
        return

    root_path.mkdir(parents=True, exist_ok=True)
    archive_path = root_path / _CIFAR_ARCHIVE
    if not archive_path.exists():
        urllib.request.urlretrieve(_CIFAR_URL, archive_path)
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=root_path)


def _load_cifar_split(root: str | Path, train: bool) -> tuple[np.ndarray, np.ndarray]:
    batch_dir = Path(root) / _CIFAR_DIRNAME
    batch_names = (
        [f"data_batch_{index}" for index in range(1, 6)] if train else ["test_batch"]
    )
    data_parts: list[np.ndarray] = []
    target_parts: list[np.ndarray] = []

    for batch_name in batch_names:
        with open(batch_dir / batch_name, "rb") as fh:
            batch = pickle.load(fh, encoding="latin1")
        data = np.asarray(batch["data"], dtype=np.uint8).reshape(-1, 3, 32, 32)
        targets = np.asarray(batch["labels"], dtype=np.int64)
        data_parts.append(data)
        target_parts.append(targets)

    return np.concatenate(data_parts, axis=0), np.concatenate(target_parts, axis=0)


def _runtime_spec() -> dict[str, float | int | str]:
    return {
        "data_seed": int(os.environ.get("AUTOSEARCH_DATA_SEED", str(DEFAULT_DATA_SEED))),
        "train_subset": int(os.environ.get("AUTOSEARCH_TRAIN_SUBSET", str(DEFAULT_TRAIN_SUBSET))),
        "val_subset": int(os.environ.get("AUTOSEARCH_VAL_SUBSET", str(DEFAULT_VAL_SUBSET))),
        "label_noise": float(os.environ.get("AUTOSEARCH_LABEL_NOISE", str(DEFAULT_LABEL_NOISE))),
        "imbalance_ratio": float(os.environ.get("AUTOSEARCH_IMBALANCE_RATIO", str(DEFAULT_IMBALANCE_RATIO))),
        "latent_mode": os.environ.get("AUTOSEARCH_LATENT_MODE", "unspecified"),
    }


def _balanced_subset_indices(targets: np.ndarray, subset_size: int, seed: int) -> list[int]:
    if subset_size <= 0 or subset_size >= len(targets):
        return list(range(len(targets)))
    rng = np.random.default_rng(seed)
    classes = np.unique(targets)
    per_class = max(1, subset_size // len(classes))
    selected: list[int] = []
    for klass in classes:
        klass_indices = np.flatnonzero(targets == klass)
        take = min(per_class, len(klass_indices))
        chosen = rng.choice(klass_indices, size=take, replace=False)
        selected.extend(int(index) for index in chosen)
    if len(selected) < subset_size:
        remaining = np.setdiff1d(np.arange(len(targets)), np.array(selected, dtype=np.int64), assume_unique=False)
        take = min(subset_size - len(selected), len(remaining))
        if take > 0:
            chosen = rng.choice(remaining, size=take, replace=False)
            selected.extend(int(index) for index in chosen)
    rng.shuffle(selected)
    return selected[:subset_size]


def _long_tail_subset_indices(targets: np.ndarray, subset_size: int, seed: int, imbalance_ratio: float) -> list[int]:
    if subset_size <= 0:
        subset_size = len(targets)
    if imbalance_ratio >= 0.999:
        return _balanced_subset_indices(targets, subset_size, seed)
    rng = np.random.default_rng(seed)
    classes = np.unique(targets)
    ratios = np.geomspace(1.0, max(float(imbalance_ratio), 1e-3), num=len(classes))
    ratios = ratios / ratios.sum()
    raw_counts = np.maximum(1, np.floor(ratios * subset_size).astype(int))
    deficit = subset_size - int(raw_counts.sum())
    if deficit > 0:
        raw_counts[:deficit] += 1
    elif deficit < 0:
        for index in range(len(raw_counts) - 1, -1, -1):
            removable = min(raw_counts[index] - 1, -deficit)
            raw_counts[index] -= removable
            deficit += removable
            if deficit == 0:
                break
    selected: list[int] = []
    for class_index, klass in enumerate(classes):
        klass_indices = np.flatnonzero(targets == klass)
        take = int(raw_counts[class_index])
        replace = take > len(klass_indices)
        if not replace:
            take = min(take, len(klass_indices))
        chosen = rng.choice(klass_indices, size=take, replace=replace)
        selected.extend(int(index) for index in chosen)
    rng.shuffle(selected)
    return selected[:subset_size]


def _apply_label_noise(targets: np.ndarray, noise_rate: float, seed: int) -> np.ndarray:
    if noise_rate <= 0.0:
        return targets
    rng = np.random.default_rng(seed)
    noisy = targets.copy()
    n = len(noisy)
    flip_count = int(round(noise_rate * n))
    if flip_count <= 0:
        return noisy
    indices = rng.choice(np.arange(n), size=flip_count, replace=False)
    for index in indices:
        original = int(noisy[index])
        replacement = int(rng.integers(0, NUM_CLASSES - 1))
        if replacement >= original:
            replacement += 1
        noisy[index] = replacement
    return noisy


class ArrayDataset(Dataset):
    def __init__(self, data: np.ndarray, targets: np.ndarray, transform=None):
        self.data = data
        self.targets = targets
        self.transform = transform

    def __len__(self) -> int:
        return int(len(self.targets))

    def __getitem__(self, index: int):
        if transforms is not None:
            image = Image.fromarray(np.transpose(self.data[index], (1, 2, 0)))
        else:
            image = torch.from_numpy(self.data[index]).float().div(255.0)
        label = int(self.targets[index])
        if self.transform is not None:
            image = self.transform(image)
        return image, label


def _load_numpy_split(train: bool) -> tuple[np.ndarray, np.ndarray]:
    if datasets is not None:
        dataset = datasets.CIFAR10(DATA_DIR, train=train, download=True)
        data = np.asarray(dataset.data, dtype=np.uint8).transpose(0, 3, 1, 2)
        targets = np.asarray(dataset.targets, dtype=np.int64)
        return data, targets
    dataset = CIFAR10Dataset(DATA_DIR, train=train, transform=None)
    return dataset.data, np.asarray(dataset.targets, dtype=np.int64)


def _build_dataset(train: bool, spec: dict[str, float | int | str], transform) -> Dataset:
    data, targets = _load_numpy_split(train=train)
    seed = int(spec["data_seed"])
    subset_size = int(spec["train_subset"] if train else spec["val_subset"])
    if train:
        indices = _long_tail_subset_indices(
            targets,
            subset_size=subset_size,
            seed=seed,
            imbalance_ratio=float(spec["imbalance_ratio"]),
        )
        subset_targets = _apply_label_noise(targets[np.array(indices, dtype=np.int64)], float(spec["label_noise"]), seed + 17)
        subset_data = data[np.array(indices, dtype=np.int64)]
        return ArrayDataset(subset_data, subset_targets, transform=transform)
    indices = _balanced_subset_indices(targets, subset_size=subset_size, seed=seed + 101)
    subset_data = data[np.array(indices, dtype=np.int64)]
    subset_targets = targets[np.array(indices, dtype=np.int64)]
    return ArrayDataset(subset_data, subset_targets, transform=transform)


def get_train_loader(
    batch_size: int,
    num_workers: int = 0,
    generator: Optional[torch.Generator] = None,
) -> DataLoader:
    """Returns training dataloader. Downloads data on first call."""
    dataset = _build_dataset(train=True, spec=_runtime_spec(), transform=_transform_train)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=True,
        generator=generator,
    )


def get_val_loader(batch_size: int = EVAL_BATCH_SIZE, num_workers: int = 0) -> DataLoader:
    """Returns validation dataloader. Downloads data on first call."""
    dataset = _build_dataset(train=False, spec=_runtime_spec(), transform=_transform_val)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,
    )


@torch.no_grad()
def evaluate_loss(model: nn.Module, device: str = "cpu") -> float:
    """Evaluate model on validation set. Returns average cross-entropy loss."""
    model.eval()
    val_loader = get_val_loader()
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    total_samples = 0
    for images, labels in val_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * images.size(0)
        total_samples += images.size(0)
    return total_loss / total_samples


@torch.no_grad()
def evaluate_accuracy(model: nn.Module, device: str = "cpu") -> float:
    """Evaluate model on validation set. Returns accuracy in [0, 1]."""
    model.eval()
    val_loader = get_val_loader()
    correct = 0
    total = 0
    for images, labels in val_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)
    return correct / total


def download_data():
    """Download CIFAR-10 if not already present."""
    if datasets is not None:
        datasets.CIFAR10(DATA_DIR, train=True, download=True)
        datasets.CIFAR10(DATA_DIR, train=False, download=True)
    else:
        _ensure_cifar_downloaded(DATA_DIR)
    print("Data ready.")


if __name__ == "__main__":
    download_data()
