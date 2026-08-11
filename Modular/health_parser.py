import json
import os
import re

import cv2
import pytesseract


class BodyScanParser:
    def __init__(self, rois_file="rois.json"):
        """Initializes the parser and dynamically loads coordinates from a JSON file."""
        self.rois = {}

        # Hardcoded defaults based on typical layout constraints
        self.default_rois = {
            "weight": [194, 304, 786, 298],
            "body_score": [72, 957, 298, 121],
            "bmi": [72, 1225, 170, 79],
            "body_fat": [609, 1206, 207, 109],
            "muscle_mass": [66, 2529, 207, 97],
            "water": [79, 2852, 188, 73],
            "bmr": [576, 2221, 230, 95],
        }

        if os.path.exists(rois_file):
            try:
                with open(rois_file) as f:
                    self.rois = json.load(f)
                print(f"✅ Successfully loaded ROIs from {rois_file}")
            except Exception as e:
                print(f"⚠️ Failed to parse {rois_file}, using defaults. Error: {e}")
                self.rois = self.default_rois
        else:
            self.rois = self.default_rois

    def clean_number(self, text):
        # Replace commas with dots (common OCR mistake for decimals) and strip newlines
        text = text.replace(",", ".").replace("..", ".").replace("\n", " ").strip()
        # Find the first sequence of digits and optional decimal point
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def parse_image(self, image_path):
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            return None

        img = cv2.imread(image_path)
        results = {}

        for key, coords in self.rois.items():
            try:
                x, y, w, h = coords
                # Add a 5px padding to the box so text isn't cut off at the edges
                x1 = max(0, x - 5)
                y1 = max(0, y - 5)
                x2 = min(img.shape[1], x + w + 5)
                y2 = min(img.shape[0], y + h + 5)

                cropped = img[y1:y2, x1:x2]

                # Resize 2x to make characters larger and clearer for Tesseract
                cropped = cv2.resize(cropped, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

                # The app uses white text on a dark background.
                # Otsu + BINARY_INV converts this to black text on a white background.
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

                # Relaxed config: No whitelist. Let it read 'kg', '%', 'kcal' naturally.
                text = pytesseract.image_to_string(thresh, config="--psm 7")

                val = self.clean_number(text)
                results[key] = val

                # Print the raw text vs the parsed number so you can debug the ROIs!
                print(f"Extracted {key}: Raw OCR = '{text.strip()}' -> Parsed = {val}")
            except Exception as e:
                print(f"Failed to parse ROI for {key}: {e}")
                results[key] = None

        return results
