"""
Object Size Estimation - Models & Dataset Downloader
Uses depth estimation + reference object (coin) to calculate real-world sizes.
Pipeline: Depth Anything V2 metric depth + known coin size -> target object size
"""
import os
import subprocess
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "object_size")
DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets", "object_size")


def download(url, dest, desc=""):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        print(f"  [skip] {desc or os.path.basename(dest)} already exists")
        return
    print(f"  [download] {desc or os.path.basename(dest)}...")
    subprocess.run(["curl", "-L", "-o", dest, url], check=False)
    print(f"  [done] {desc}")


def install_deps():
    print("\n=== Installing Dependencies ===")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                     "torch", "torchvision", "opencv-python", "pillow",
                     "huggingface_hub", "numpy", "scipy"], check=False)


def download_models():
    print("\n=== Downloading Metric Depth Models ===")
    os.makedirs(MODELS_DIR, exist_ok=True)

    # ZoeDepth for metric depth (outputs meters directly)
    print("\n--- ZoeDepth (metric depth in meters) ---")
    print("  [info] Install ZoeDepth:")
    print("         pip install git+https://github.com/isl-org/ZoeDepth.git")
    print("  [info] Model auto-downloads on first use via torch.hub")

    # Depth Anything V2 metric checkpoints
    print("\n--- Depth Anything V2 Metric Depth ---")
    metric_models = [
        ("dpt_vitl14_nyu.ckpt",
         "https://github.com/DepthAnything/Depth-Anything-V2/releases/download/metric_depth/dpt_vitl14_nyu.ckpt",
         "DA2 Metric NYU (indoor, 0.2-10m)"),
        ("dpt_vitl14_kitti.ckpt",
         "https://github.com/DepthAnything/Depth-Anything-V2/releases/download/metric_depth/dpt_vitl14_kitti.ckpt",
         "DA2 Metric KITTI (outdoor, 0-80m)"),
    ]
    for filename, url, desc in metric_models:
        download(url, os.path.join(MODELS_DIR, filename), desc)


def download_datasets():
    print("\n=== Downloading Object Dimension Datasets ===")
    os.makedirs(DATASETS_DIR, exist_ok=True)

    print("\n--- Objectron (15K videos, 4M+ images, 9 categories) ---")
    objectron_dir = os.path.join(DATASETS_DIR, "objectron")
    print(f"  [info] Objectron: https://github.com/google-research-datasets/Objectron")
    print(f"         Download via: gsutil -m cp -R gs://objectron/{category} {objectron_dir}/")

    print("\n--- CO3D (Meta) ---")
    print("  [info] CO3D: https://ai.meta.com/datasets/CO3D-dataset/")
    print("         1.5M frames, 19K videos, 50 COCO categories")

    print("\n--- OmniObject3D ---")
    print("  [info] OmniObject3D: https://huggingface.co/papers/2301.07525")
    print("         6,000 real-scanned 3D objects, 190 categories")


def create_measurement_script():
    script_path = os.path.join(MODELS_DIR, "measure.py")
    if os.path.exists(script_path):
        return
    script = '''"""
Object Size Estimation using Depth + Reference Object

Pipeline:
1. Detect reference object (coin) in image
2. Get depth map from Depth Anything V2 metric model
3. Compute scale factor from reference
4. Apply to target object

Known reference sizes:
- US Quarter: 24.26mm diameter
- Euro 1 coin: 23.25mm diameter
- British 1 Pound: 23.43mm diameter
- Iranian 1000 Rial: 26mm diameter
"""
import cv2
import numpy as np

REFERENCE_SIZES_MM = {
    "us_quarter": 24.26,
    "euro_1": 23.25,
    "british_1pound": 23.43,
    "iranian_1000rial": 26.0,
    "iranian_500rial": 23.0,
    "dime": 17.91,
    "penny": 19.05,
    "nickel": 21.21,
}


def measure_by_reference(image_path, ref_type="euro_1", target_bbox=None):
    """Measure object size using reference object at same depth."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, 1, 50,
        param1=50, param2=30, minRadius=15, maxRadius=150
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        cx, cy, cr = circles[0][0]
        ref_pixel_diameter = cr * 2
    else:
        print("No circle detected. Manual measurement mode.")
        print(f"Image size: {image.shape[1]}x{image.shape[0]} pixels")
        ref_pixel_diameter = float(input("Enter reference object pixel diameter: "))

    ref_real_mm = REFERENCE_SIZES_MM.get(ref_type, 24.26)
    pixels_per_mm = ref_pixel_diameter / ref_real_mm

    print(f"Reference: {ref_type} = {ref_real_mm}mm")
    print(f"Pixel diameter: {ref_pixel_diameter:.1f}px")
    print(f"Scale: {pixels_per_mm:.2f} px/mm")
    return pixels_per_mm


def measure_with_depth(image_path, depth_model, ref_bbox, target_bbox, ref_real_mm=24.26):
    """Measure using metric depth model for different-depth objects."""
    image = cv2.imread(image_path)
    depth = depth_model.infer_image(image)

    ref_depth = np.mean(depth[ref_bbox[1]:ref_bbox[1]+ref_bbox[3],
                                ref_bbox[0]:ref_bbox[0]+ref_bbox[2]])
    target_depth = np.mean(depth[target_bbox[1]:target_bbox[1]+target_bbox[3],
                                   target_bbox[0]:target_bbox[0]+target_bbox[2]])

    ref_pixel_w = ref_bbox[2]
    target_pixel_w = target_bbox[2]

    scale = (ref_real_mm * ref_depth) / (ref_pixel_w * target_depth)
    target_real_mm = target_pixel_w * scale

    return {
        "target_width_mm": round(target_real_mm, 2),
        "target_width_cm": round(target_real_mm / 10, 2),
        "ref_depth_m": round(ref_depth, 3),
        "target_depth_m": round(target_depth, 3),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python measure.py <image_path> [reference_type]")
        print(f"Reference types: {list(REFERENCE_SIZES_MM.keys())}")
        sys.exit(1)
    ref_type = sys.argv[2] if len(sys.argv) > 2 else "euro_1"
    scale = measure_by_reference(sys.argv[1], ref_type)
    print(f"\\nPlace reference object and target at same depth for best accuracy.")
'''
    with open(script_path, "w") as f:
        f.write(script)
    print(f"  [created] {script_path}")


if __name__ == "__main__":
    install_deps()
    download_models()
    download_datasets()
    create_measurement_script()
    print("\n=== Object Size Estimation Setup Complete ===")
    print(f"Models saved to: {MODELS_DIR}")
    print("Usage: python measure.py <image_path> [reference_type]")
