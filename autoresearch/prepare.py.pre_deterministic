"""Fixed constants, data download, and evaluation harness.
DO NOT MODIFY - this is read-only for the agent.
"""

from __future__ import annotations

import os
import pickle
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

try:
    from torchvision import datasets, transforms  # type: ignore
except ModuleNotFoundError:
    datasets = None
    transforms = None


# --- Constants ---------------------------------------------------------------
TIME_BUDGET = 120
EVAL_BATCH_SIZE = 256
NUM_CLASSES = 10
INPUT_CHANNELS = 3
IMAGE_SIZE = 32
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

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


def get_train_loader(batch_size: int, num_workers: int = 2) -> DataLoader:
    """Returns training dataloader. Downloads data on first call."""
    if datasets is not None:
        dataset = datasets.CIFAR10(
            DATA_DIR, train=True, download=True, transform=_transform_train
        )
    else:
        dataset = CIFAR10Dataset(DATA_DIR, train=True, transform=_transform_train)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=True,
    )


def get_val_loader(batch_size: int = EVAL_BATCH_SIZE, num_workers: int = 2) -> DataLoader:
    """Returns validation dataloader. Downloads data on first call."""
    if datasets is not None:
        dataset = datasets.CIFAR10(
            DATA_DIR, train=False, download=True, transform=_transform_val
        )
    else:
        dataset = CIFAR10Dataset(DATA_DIR, train=False, transform=_transform_val)
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
