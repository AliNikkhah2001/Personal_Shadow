# Computer Vision Food Calorie / Weight / Size Estimation — Research Notes

Date: 2026-08-12 · Branch: `feat/calorie-vision-research`

## 1. Canonical projects & papers

| Project | What it does | Useful feature for us |
|---|---|---|
| **Im2Calories** (Myers et al., Google, ICCV 2015) — [paper](https://arxiv.org/abs/1602.03692) | Segmentation + depth/volume from a single image, nutrition DB lookup, both "restaurant known" and "generic" settings | Volume estimation from single RGB; food-name → nutrition lookup chain |
| **Nutrition5k** (Google Research, CVPR 2021) — [repo](https://github.com/google-research-datasets/Nutrition5k), [paper](https://arxiv.org/abs/2103.03375) | 5,066 dishes with RGB + depth video + component **weights** + accurate kcal/macros; models outperform nutritionists; available on [Kaggle mirror](https://www.kaggle.com/datasets/gillesokhin/nutrition5k-dataset) | Depth improves portion accuracy; benchmark for weight/calorie regression |
| **ECUSTFD** (Liang et al., 2017) — [code](https://github.com/Liang-yc/CalorieEstimation), [resized dataset](https://github.com/Liang-yc/ECUSTFD-resized-) | Food image dataset with **volume and mass annotations** | Direct ground truth for volume/weight testing |
| **WhiteXiezx/Food-Volume-Estimation** (MIT) — [repo](https://github.com/WhiteXiezx/Food-Volume-Estimation) | Inception-ResNet-V2 detection + RefineNet segmentation + **monocular depth** (NYU-Depth-V2 pretrained) + **plate diameter prior** → volume cm³ | Plate as scale anchor (we already do this); depth model as future upgrade |
| **Faster R-CNN + MobileNetV3 weight estimation** (2024) — [paper](https://arxiv.org/abs/2405.16478) | 2,380 images / 14 foods; detection mAP 83.41 %, weight R² 98.65 % | Weight regression trained on portions (alternative to density math) |
| **Sensors 2024, "Automated Food Weight…"** (MDPI) — [paper](https://www.mdpi.com/1424-8220/24/23/7660) | YOLOv8L-Seg + RGB-D depth → volume, **per-food density tables** → weight; rice 5.07 %, chicken 3.75 % error; introduces volume→weight look-up tables | Density tables validated; linear volume↔weight relationship |
| **Meal Analysis with Theseus** (lannguyen0910) — [repo](https://github.com/lannguyen0910/food-recognition) | YOLOv5-v8 trained on aggregated food datasets; **YOLOv8s mAP 0.963** @0.5 IoU | Pre-trained food detection weights / training recipe |
| **food-detection-nutrition-yolov8** (MIT) — [repo](https://github.com/shashwat7031/food-detection-nutrition-yolov8) | YOLOv8n fine-tuned on Food-101 (101 food classes) + USDA FoodData Central API | Ready-made fine-tune pipeline + nutrition API |
| **BinhQuocNguyen/food-recognition-model** (MIT, HF) — [model](https://huggingface.co/BinhQuocNguyen/food-recognition-model) | EfficientNet-B0 101-class classifier + YOLO v8 detection + portion size + USDA; classification >85 %, calorie ±20 % | Food **name** mapping (101 classes) with USDA per-100g |
| **VolE / Foodkit** (Sci. Reports 2026) — [paper](https://www.nature.com/articles/s41598-026-38756-5) | Reference- and depth-free volume via ARCore/ARKit + SfM point clouds; 21 food objects with ground-truth volumes/masses | SfM path for phones with AR (future) |
| **Hungry Networks / MMAsia'20** — [paper](http://www.mm.inf.uec.ac.jp/pub/conf20/210307naritomi_0.pdf) | 3D dish mesh reconstruction from single image (size-normalized) | 3D normalization ideas |

Survey worth reading: *Food Calorie Estimation Using Computer Vision: A Comparative Review* (2025) — [PDF](https://medic.upm.edu.my/upload/dokumen/20251124143106A27_RA1_MJMHS_0469.pdf), and the 2026 portion-estimation survey *Food Portion Estimation: From Pixels to Calories* ([arXiv](https://arxiv.org/html/2602.05078)).

## 2. The core problem: scale ambiguity

> "Without a known reference, a small pizza close to the camera is geometrically indistinguishable from a large pizza further away." — *Food Portion Estimation: From Pixels to Calories* (2026)

Every reliable single-image method resolves it with **at least one** of:

1. **Fiducial reference objects** of known size — coin, checkerboard, **credit card**, fork/thumb (Im2Calories review, ECUSTFD).
   → We already detect credit card (aspect 1.586) and standard plate (26 cm ellipse). **Next: coin detection** (small circle, 2.43/2.58 cm) for close-ups.
2. **Known plate/dish diameter as scale prior** (WhiteXiezx, MMAsia 2021).
   → We use the plate ellipse. Enhancement: allow user-supplied plate diameter.
3. **Depth sensors / RGB-D** (Kinect, RealSense, phone LiDAR; Nutrition5k, Sensors 2024) — 3.75–5.07 % weight error.
   → Future hardware upgrade; keep a pluggable depth channel.
4. **Monocular depth prediction + back-projection** (Im2Calories, NYU-V2 pretrained models) — no hardware, but needs a trained network.
   → Future ML upgrade (documented in `load_models()`).
5. **Reference-free SfM/AR** (VolE) — needs multi-view capture.

## 3. From volume to calories

Consensus chain: **segmentation mask → area (px²) → scale → area (cm²) → height/depth → volume (cm³) → density → weight (g) → kcal/macros per 100 g**

- Weight = volume × density; densities are per-food-type and validated as linear (Sensors 2024).
- Calorie = weight × (kcal per 100 g) / 100 from a nutrition DB (USDA FoodData Central, Edamam, or our own `ingredients` table).
- Model-based alternative: train a **weight regression head** (MobileNetV3 style, MAPE 0.064 %) instead of geometric math — better once labeled portion data exists (Nutrition5k Kaggle mirror).

## 4. Datasets for testing performance

| Dataset | Classes / size | Annotations | Use |
|---|---|---|---|
| **Food-101** — [link](https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/) | 101 / 101,000 | class label only | classification / name mapping |
| **Nutrition5k** — [Kaggle](https://www.kaggle.com/datasets/gillesokhin/nutrition5k-dataset) | ~5,066 dishes | RGB + depth + component weights + kcal | weight/calorie benchmark |
| **ECUSTFD** — [resized](https://github.com/Liang-yc/ECUSTFD-resized-) | single-item plates | **volume + mass** ground truth | volume/weight eval |
| **Food Recognition 2022** — [DatasetNinja](https://datasetninja.com/food-recognition) | 43,962 imgs / 498 classes | instance segmentation | detection/segmentation eval |
| **Open Images V6 Food** subset | 20,000+ / 18 food labels | boxes | YOLO training |
| **OmniFood8K** (CVPR 2026) | 8,036 / 165 + 115k synth | detection + quantity | quantity estimation |
| **Food-2K** | 2,000 / 1,036,564 | class labels | large-scale classifier |

Practical entry: **Food-101 test split** (25,250 images, no labels needed for our heuristic engine) to sanity-check detection rate, plus a small hand-labeled set of ~20 photos (15 taken with a printed credit card, 5 with a plain plate) for true-size accuracy.

## 5. What we adopted / what is next

**Adopted in this branch:**
- Coin reference object (US quarter 2.43 cm) — small-circle detection for close-up shots.
- **Food-name mapping**: detected class → concrete food name resolved from the `ingredients` DB (Persian keyword match, else canonical English class name) → `food_name` in every detection payload and on annotated images.
- Batch evaluation tool `tools/evaluate_calorie_vision.py` — annotated outputs + CSV results.
- Sample image pipeline `tools/fetch_sample_images.py` — CC-licensed Wikimedia Commons food photos.

**Future (documented hooks):**
- `FoodCalorieEstimator.load_models()` — plug in YOLOv8s (`lannguyen0910` recipe, mAP 0.963) or EfficientNet-B0 (HF model) for real food names (101 classes).
- Monocular depth channel (NYU-V2 style) replacing flat-height assumption.
- Calibrated per-food volume→weight regression on Nutrition5k/ECUSTFD instead of fixed densities.