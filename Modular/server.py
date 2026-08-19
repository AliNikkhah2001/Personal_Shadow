"""Flask API server for Food Vision System.

Provides endpoints for:
- Running YOLOv8-seg + MiDaS food detection on images
- Returning bounding boxes, segmentation masks, confidence scores
- Size/volume/weight estimation with reference object calibration
- Calorie/macros estimation from USDA-based nutrition database
- Reference object calibration (credit card, quarter coin)
"""

from __future__ import annotations

import base64
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Initialize detector - may take moment for MiDaS download
detector = None


def init_detector():
    """Initialize the food detector (called on server start)."""
    global detector
    if detector is None:
        try:
            from food_vision_complete.model import FoodDetector
            detector = FoodDetector(
                model_name='yolov8n-seg.pt',
                usda_nutrition_path='data/datasets/nutrition_db.json'
            )
            print("✓ FoodVision server initialized with full pipeline")
        except Exception as e:
            print(f"⚠ Server init warning: {e}")
            try:
                from food_vision_complete.model import YOLOv8SegWrapper
                from opencv_calorie_estimator import FoodCalorieEstimator
                detector = type('SimpleDetector', (), {
                    'detect_and_analyze': lambda self, img, **kw: (
                        img,
                        type('Results', (), {
                            'class_names': [],
                            'confidences': [],
                            'boxes': [],
                        })()
                    ),
                    'state': type('State', (), {
                        'pixels_per_cm': 8.0,
                        'reference_calibrated': False
                    })()
                })()
                detector = FoodDetector(model_name='yolov8n-seg.pt')
                print("✓ FoodVision server initialized (basic mode)")
            except Exception as e2:
                print(f"✗ Server init failed completely: {e2}")
                detector = None


@app.route('/')
def index():
    return send_from_directory('static', 'server_test.html')


@app.route('/test')
def test():
    """Health check endpoint."""
    if detector is None:
        init_detector()
    if detector is None:
        return jsonify({'status': 'initializing', 'ready': False})
    return jsonify({
        'status': 'ready',
        'ready': True,
        'classes': len(detector.nutrition_db) if detector.nutrition_db else 0,
        'reference_calibrated': detector.state.reference_calibrated if hasattr(detector, 'state') and hasattr(detector.state, 'reference_calibrated') else False
    })


@app.route('/detect', methods=['POST'])
def detect():
    """Run food detection on submitted image."""
    global detector

    if detector is None:
        init_detector()

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        import numpy as np
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400

        calibrate = request.form.get('calibrate', 'false').lower() == 'true'

        annotated, results = detector.detect_and_analyze(
            frame,
            calibrate_reference=calibrate
        )

        result_list = []
        for det in results:
            result_dict = {
                'class_name': det.class_name,
                'confidence': det.confidence,
                'bbox': det.bbox,
                'size_info': det.size_info,
                'calorie_info': det.calorie_info,
            }
            result_list.append(result_dict)

        _, buffer = cv2.imencode('.jpg', annotated)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({
            'success': True,
            'results': result_list,
            'annotated_image': img_base64,
            'pixels_per_cm': detector.state.pixels_per_cm if hasattr(detector, 'state') else 8.0,
            'reference_calibrated': detector.state.reference_calibrated if hasattr(detector, 'state') else False
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/calibrate', methods=['POST'])
def calibrate():
    """Calibrate reference object from image."""
    global detector

    if detector is None:
        init_detector()

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        import numpy as np
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400

        annotated, results = detector.detect_and_analyze(frame, calibrate_reference=True)

        ref_status = "none"
        if detector.state and hasattr(detector.state, 'reference_calibrated'):
            if detector.state.reference_calibrated:
                ref_status = f"{detector.state.pixels_per_cm:.2f} px/cm"

        _, buffer = cv2.imencode('.jpg', annotated)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({
            'success': True,
            'reference_status': ref_status,
            'annotated_image': img_base64,
            'pixels_per_cm': detector.state.pixels_per_cm if hasattr(detector, 'state') else 8.0
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


# Serve test HTML at root
@app.route('/server_test.html')
def server_test():
    return send_from_directory('static', 'server_test.html')


if __name__ == '__main__':
    init_detector()

    static_dir = PROJECT_ROOT / 'static'
    static_dir.mkdir(exist_ok=True)

    html_path = static_dir / 'server_test.html'
    if not html_path.exists():
        html_path.write_text('''
<!DOCTYPE html>
<html>
<head>
    <title>Food Vision System - Server Test</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
        .status { padding: 10px; border-radius: 5px; margin: 20px 0; }
        .ready { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .info { background: #d6d8dd; color: #383d41; border: 1px solid #adb5bd; }
        img { max-width: 100%; height: auto; }
        .controls { margin: 20px 0; }
        button { padding: 8px 16px; margin: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Food Vision System API Test</h1>

    <div class="status" id="status">Status: Initializing...</div>

    <div class="info">
        <h3>Endpoints</h3>
        <ul>
            <li><code>GET /</code> - This page</li>
            <li><code>GET /test</code> - Health check</li>
            <li><code>POST /detect</code> - Run detection on image</li>
            <li><code>POST /calibrate</code> - Calibrate reference object</li>
        </ul>
    </div>

    <div class="controls">
        <h3>Test Detection</h3>
        <input type="file" id="imageInput" accept="image/*">
        <button onclick="runDetection()">Run Detection</button>
        <button onclick="checkHealth()">Health Check</button>
        <br><br>
        <span>Calibrate reference:</span>
        <input type="checkbox" id="calibrateCheck"> Calibrate reference object
        <button onclick="runCalibration()">Calibrate</button>
    </div>

    <h3>Results</h3>
    <div id="results" style="display:none; margin-top:20px;">
        <h4>Detected Food Items</h4>
        <ul id="detectionList"></ul>
        <p>Pixels per cm: <span id="ppm">--</span></p>
        <p>Reference calibrated: <span id="refStatus">--</span></p>
    </div>

    <h3>Annotated Image</h3>
    <img id="resultImage" alt="Annotated result" style="margin-top:10px; display:none;">
    <p><a id="downloadLink" download="food_results.jpg" style="display:none;">Download Results</a></p>

    <script>
        function show(element) {
            element.style.display = 'block';
        }
        function hide(element) {
            element.style.display = 'none';
        }

        function updateStatus(text, className) {
            const status = document.getElementById('status');
            status.innerText = 'Status: ' + text;
            status.className = 'status ' + className;
        }

        function runDetection() {
            const file = document.getElementById('imageInput').files[0];
            const calibrate = document.getElementById('calibrateCheck').checked;
            const formData = new FormData();
            formData.append('image', file);
            if (calibrate) formData.append('calibrate', 'true');

            fetch('/detect', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    updateStatus(data.error, 'error');
                    alert('Error: ' + data.error);
                    return;
                }

                updateStatus('Detection complete', 'ready');

                const list = document.getElementById('detectionList');
                list.innerHTML = '';

                if (data.results && data.results.length > 0) {
                    data.results.forEach((r, i) => {
                        const li = document.createElement('li');
                        li.innerHTML = `
                            <strong>${r.class_name}</strong> (${r.confidence.toFixed(2)} conf)<br>
                            Calories: ${r.calorie_info ? r.calorie_info.calories + ' kcal' : 'N/A'}<br>
                            Weight: ${r.calorie_info ? r.calorie_info.weight_g + ' g' : 'N/A'}<br>
                            Volume: ${r.size_info ? r.size_info.volume_cm3 + ' cm³' : 'N/A'}<br>
                            Size: ${r.size_info ? r.size_info.width_cm + '×' + r.size_info.height_cm + ' cm²' : 'N/A'}
                        `;
                        list.appendChild(li);
                    });
                } else {
                    list.innerHTML = '<li>No food items detected</li>';
                }

                const img = document.getElementById('resultImage');
                img.src = 'data:image/jpg;base64,' + data.annotated_image;
                show(img);
                show(document.getElementById('results'));

                document.getElementById('ppm').innerText = data.pixels_per_cm.toFixed(2);

                const refStatus = document.getElementById('refStatus');
                refStatus.innerText = data.reference_calibrated ? 'Yes' : 'No';
                if (data.reference_calibrated) {
                    refStatus.innerText += ` (${data.pixels_per_cm.toFixed(2)} px/cm)`;
                }

                show(document.getElementById('results'));
                show(document.getElementById('downloadLink'));
            })
            .catch(error => {
                updateStatus('Error: ' + error.message, 'error');
                console.error('Error:', error);
            });
        }

        function checkHealth() {
            fetch('/test')
            .then(response => response.json())
            .then(data => {
                updateStatus(data.status || 'unknown', data.ready ? 'ready' : 'initializing');
                console.log('Health check:', data);
            })
            .catch(error => {
                updateStatus('Cannot connect', 'error');
                console.error('Error:', error);
            });
        }

        function runCalibration() {
            const file = document.getElementById('imageInput').files[0];
            if (!file) {
                alert('Please select an image first');
                return;
            }

            const formData = new FormData();
            formData.append('image', file);

            fetch('/calibrate', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }

                updateStatus('Calibration ' + data.ref_status, 'ready');

                const img = document.getElementById('resultImage');
                img.src = 'data:image/jpg;base64,' + data.annotated_image;
                show(img);
            })
            .catch(error => {
                alert('Error: ' + error.message);
                console.error('Error:', error);
            });
        }
    </script>
</body>
</html>
''')

    print("\nStarting FoodVision Server...")
    print("=" * 50)
    print("API Endpoints:")
    print("  GET  /           - Web interface")
    print("  GET  /test       - Health check")
    print("  POST /detect     - Run food detection")
    print("  POST /calibrate  - Calibrate reference object")
    print("=" * 50)
    print("\nOpen your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server\n")

    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)