"""
Face Recognition Engine for AI Assistant
Handles face detection, encoding, registration, and identification
"""

import face_recognition
import cv2
import json
import os
import time
import numpy as np
from threading import Lock
import logging

logger = logging.getLogger(__name__)

# Global camera lock to prevent concurrent access
camera_lock = Lock()


class FaceRecognitionEngine:
    """Core engine for face recognition with caching support"""

    def __init__(self, db_path='known_faces.json'):
        self.db_path = db_path
        self.known_encodings = {}  # {name: [encoding1, encoding2, ...]}
        self.last_seen = None  # {name: str, timestamp: float, confidence: float}
        self.cache_ttl = 30  # detik
        self.lock = Lock()
        self.load_database()

    def load_database(self):
        """Load face encodings dari JSON file"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    for name, encodings in data.items():
                        self.known_encodings[name] = [
                            np.array(enc) for enc in encodings
                        ]
                logger.info(f"Loaded {len(self.known_encodings)} face encodings from {self.db_path}")
            else:
                logger.info(f"No face database found at {self.db_path}, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load face database: {e}")

    def save_database(self):
        """Save face encodings ke JSON file"""
        try:
            with self.lock:
                data = {
                    name: [enc.tolist() for enc in encodings]
                    for name, encodings in self.known_encodings.items()
                }
                with open(self.db_path, 'w') as f:
                    json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} face encodings to {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to save face database: {e}")

    def register_face(self, name, images):
        """
        Daftarkan wajah baru dari multiple images

        Args:
            name: str - nama orang
            images: list of cv2 images (BGR format)

        Returns:
            dict: {success: bool, message: str, sample_count: int}
        """
        try:
            encodings = []
            for i, img in enumerate(images):
                # Convert BGR to RGB
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # Detect and encode face
                face_encodings = face_recognition.face_encodings(rgb)
                if face_encodings:
                    encodings.append(face_encodings[0])
                    logger.debug(f"Face {i+1}/{len(images)} encoded successfully")
                else:
                    logger.warning(f"No face detected in image {i+1}/{len(images)}")

            # Require at least 3 successful encodings
            if len(encodings) < 3:
                return {
                    'success': False,
                    'message': f'Gagal: hanya {len(encodings)} wajah terdeteksi (minimal 3)',
                    'sample_count': len(encodings)
                }

            # Save to database
            with self.lock:
                self.known_encodings[name] = encodings

            self.save_database()

            logger.info(f"Successfully registered {name} with {len(encodings)} samples")
            return {
                'success': True,
                'message': f'Berhasil mendaftarkan {name} dengan {len(encodings)} sample',
                'sample_count': len(encodings)
            }

        except Exception as e:
            logger.error(f"Failed to register face: {e}")
            return {
                'success': False,
                'message': f'Error saat registrasi: {str(e)}',
                'sample_count': 0
            }

    def identify_face(self, image):
        """
        Identifikasi wajah dalam image

        Args:
            image: cv2 image (BGR format)

        Returns:
            dict: {name: str, distance: float, confidence: float} atau None
        """
        try:
            # Convert BGR to RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Detect face locations first (avoids redundant detection inside face_encodings)
            face_locations = face_recognition.face_locations(rgb)
            if not face_locations:
                return None

            # Encode faces using pre-detected locations
            face_encodings = face_recognition.face_encodings(rgb, face_locations)

            if not face_encodings:
                return None

            # Use first face detected
            face_encoding = face_encodings[0]

            # Deep copy known_encodings under lock for thread safety
            with self.lock:
                known_encodings_copy = {
                    name: [enc.copy() for enc in encodings]
                    for name, encodings in self.known_encodings.items()
                }

            # Compare with known faces (using copy, no lock needed)
            best_match = None
            best_distance = 1.0

            for name, known_encodings in known_encodings_copy.items():
                # Calculate distances to all encodings of this person
                distances = face_recognition.face_distance(known_encodings, face_encoding)
                # Use min_distance for more conservative matching (avoids false positives from averaging)
                min_distance = distances.min()

                # Track best match
                if min_distance < best_distance:
                    best_distance = min_distance
                    best_match = name

            # Threshold: distance < 0.6 = match (face_recognition default)
            if best_match and best_distance < 0.6:
                confidence = (1 - best_distance) * 100
                return {
                    'name': best_match,
                    'distance': best_distance,
                    'confidence': confidence
                }

            return None

        except Exception as e:
            logger.error(f"Failed to identify face: {e}")
            return None

    def update_cache(self, result):
        """Update last_seen cache"""
        if result:
            with self.lock:
                self.last_seen = {
                    'name': result['name'],
                    'timestamp': time.time(),
                    'confidence': result['confidence']
                }
                logger.debug(f"Cache updated: {result['name']} ({result['confidence']:.1f}%)")

    def get_cached_person(self):
        """
        Get person dari cache jika masih valid (< 30 detik)

        Returns:
            dict: {name: str, confidence: float} atau None
        """
        with self.lock:
            if self.last_seen:
                age = time.time() - self.last_seen['timestamp']
                if age < self.cache_ttl:
                    return {
                        'name': self.last_seen['name'],
                        'confidence': self.last_seen['confidence']
                    }
                else:
                    logger.debug(f"Cache expired (age: {age:.1f}s)")
        return None

    def list_registered(self):
        """List semua wajah terdaftar"""
        with self.lock:
            return {
                name: len(encodings)
                for name, encodings in self.known_encodings.items()
            }


def background_face_scanner(engine, socketio, stop_flag):
    """
    Thread function untuk background scanning

    Args:
        engine: FaceRecognitionEngine instance
        socketio: SocketIO instance
        stop_flag: threading.Event to stop the scanner
    """
    logger.info("Background face scanner started")

    while not stop_flag.is_set():
        try:
            # Capture dari kamera — keep lock scope minimal (open+read+release only)
            camera_available = False
            with camera_lock:
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    # Allow camera to warm up
                    time.sleep(0.3)
                    ret, frame = cap.read()
                    camera_available = True
                    cap.release()
                else:
                    cap.release()

            if not camera_available:
                logger.debug("Camera not available, retrying in 5s")
                # Use stop_flag.wait() instead of time.sleep() — wakes instantly on stop
                if stop_flag.wait(timeout=5):
                    break
                continue

            if not ret or frame is None:
                logger.debug("Failed to capture frame, retrying in 5s")
                if stop_flag.wait(timeout=5):
                    break
                continue

            # Identify face (outside lock — no blocking other camera users)
            result = engine.identify_face(frame)

            if result:
                engine.update_cache(result)

                # Emit ke frontend
                socketio.emit('face_detected', {
                    'name': result['name'],
                    'confidence': result['confidence']
                })

                logger.info(f"Face detected: {result['name']} ({result['confidence']:.1f}%)")

        except Exception as e:
            # Log error tapi jangan crash thread
            logger.warning(f"Background scanner error: {e}")

        # Wait before next scan — use stop_flag.wait() for instant shutdown
        if stop_flag.wait(timeout=5):
            break

    logger.info("Background face scanner stopped")
