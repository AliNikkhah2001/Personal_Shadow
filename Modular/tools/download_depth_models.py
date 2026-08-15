"""
Depth Anything V2 - Model & Dataset Downloader
Downloads lightweight depth estimation models for local inference.
Best model: Depth Anything V2 Small (24.8M params, ~99MB, Apache-2.0)
"""
import os
import sys
import subprocess
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "depth")
DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets", "depth")


def download(url, dest, desc=""):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        print(f"  [skip] {desc or os.path.basename(dest)} already exists")
        return
    print(f"  [download] {desc or os.path.basename(dest)}...")
    try:
        urllib.request.urlretrieve(dest)
    except Exception:
        subprocess.run(["curl", "-L", "-o", dest, url], check=False)
    print(f"  [done] {desc}")


def install_deps():
    print("\n=== Installing Dependencies ===")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                     "torch", "torchvision", "transformers", "huggingface_hub",
                     "opencv-python", "pillow", "timm"], check=False)


def download_models():
    print("\n=== Downloading Depth Anything V2 Models ===")
    os.makedirs(MODELS_DIR, exist_ok=True)

    models = [
        ("depth_anything_v2_vits.pth",
         "https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth",
         "Depth Anything V2 Small (24.8M, ~99MB, Apache-2.0)"),
        ("depth_anything_v2_vitb.pth",
         "https://huggingface.co/depth-anything/Depth-Anything-V2-Base/resolve/main/depth_anything_v2_vitb.pth",
         "Depth Anything V2 Base (97.5M, ~390MB)"),
    ]

    for filename, url, desc in models:
        download(url, os.path.join(MODELS_DIR, filename), desc)

    # Also download MiDaS lightweight
    print("\n=== Downloading MiDaS Models ===")
    midas_models = [
        ("dpt_swin2_tiny_256.pt",
         "https://github.com/isl-org/MiDaS/releases/download/v3_1/dpt_swin2_tiny_256.pt",
         "MiDaS DPT SwinV2 Tiny (40.9M, ~164MB)"),
    ]
    for filename, url, desc in midas_models:
        download(url, os.path.join(MODELS_DIR, filename), desc)


def download_datasets():
    print("\n=== Downloading Depth Datasets ===")
    os.makedirs(DATASETS_DIR, exist_ok=True)

    nyu_dir = os.path.join(DATASETS_DIR, "nyu_depth_v2")
    if not os.path.exists(nyu_dir):
        print("  [info] NYU Depth V2: download from https://huggingface.co/datasets/sayakpaul/nyu_depth_v2")
        print("         or https://www.kaggle.com/datasets/soumikrakshit/nyu-depth-v2")
    else:
        print("  [skip] NYU Depth V2 exists")

    kitti_dir = os.path.join(DATASETS_DIR, "kitti")
    if not os.path.exists(kitti_dir):
        print("  [info] KITTI Depth: download annotated depth (14GB) from:")
        print("         https://s3.eu-central-1.amazonaws.com/avg-kitti/data_depth_annotated.zip")
    else:
        print("  [skip] KITTI exists")


def create_inference_script():
    script_path = os.path.join(MODELS_DIR, "inference.py")
    if os.path.exists(script_path):
        return
    script = '''"""Depth Anything V2 - Local Inference Script"""
import cv2
import numpy as np
import torch
from PIL import Image
import os, sys

MODEL_DIR = os.path.join(os.path.dirname(__file__))

def load_model(size="vits", device=None):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    configs = {
        "vits": {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384]},
        "vitb": {"encoder": "vitb", "features": 128, "out_channels": [96, 192, 384, 768]},
    }
    sys.path.insert(0, os.path.join(MODEL_DIR, "..", ".."))
    from depth_anything_v2.dpt import DepthAnythingV2
    model = DepthAnythingV2(**configs[size])

    weight_file = os.path.join(MODEL_DIR, f"depth_anything_v2_{size}.pth")
    if os.path.exists(weight_file):
        model.load_state_dict(torch.load(weight_file, map_location="cpu"))
    else:
        print(f"Weights not found at {weight_file}, run download_models() first")
    model.eval().to(device)
    return model, device

def predict(model, image_path, device="cpu"):
    raw_img = cv2.imread(image_path)
    depth = model.infer_image(raw_img)
    depth_norm = (depth - depth.min()) / (depth.max() - depth.min()) * 255
    return depth_norm.astype(np.uint8), depth

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inference.py <image_path>")
        sys.exit(1)
    model, device = load_model("vits")
    depth_norm, depth_raw = predict(model, sys.argv[1], device)
    Image.fromarray(depth_norm).save("depth_output.png")
    print("Saved depth_output.png")
'''
    with open(script_path, "w") as f:
        f.write(script)
    print(f"  [created] {script_path}")


if __name__ == "__main__":
    install_deps()
    download_models()
    download_datasets()
    create_inference_script()
    print("\n=== Depth Estimation Setup Complete ===")
    print(f"Models saved to: {MODELS_DIR}")
    print("Usage: python inference.py <image_path>")
