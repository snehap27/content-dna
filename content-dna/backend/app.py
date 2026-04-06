import json
import os
import sys
import time
import uuid

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, jsonify, request
from backend.utils import ensure_dir, save_uploaded_file
from backend.fingerprint import fingerprint_media
from backend.similarity import match_fingerprints

UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'db.json')
ensure_dir(UPLOAD_DIR)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024


def load_db():
    if not os.path.exists(DB_PATH):
        return {'items': []}
    with open(DB_PATH, 'r', encoding='utf-8') as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            data = {'items': []}
    if 'items' not in data:
        data['items'] = []
    return data


def save_db(data):
    with open(DB_PATH, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'timestamp': int(time.time())})


@app.route('/store-official', methods=['POST'])
def store_official():
    if 'file' not in request.files:
        return jsonify({'error': 'Missing file upload.'}), 400

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400

    dest_dir = os.path.join(UPLOAD_DIR, 'official')
    dest_path = save_uploaded_file(uploaded_file, dest_dir, prefix=str(uuid.uuid4()))

    try:
        fingerprint, media_type = fingerprint_media(dest_path, fps=1)
    except Exception as exc:
        return jsonify({'error': 'Failed to fingerprint media.', 'details': str(exc)}), 500

    db = load_db()
    item = {
        'id': str(uuid.uuid4()),
        'filename': os.path.basename(dest_path),
        'path': os.path.relpath(dest_path, BASE_DIR),
        'media_type': media_type,
        'title': request.form.get('title', os.path.basename(dest_path)),
        'fingerprint': fingerprint.tolist(),
        'created_at': int(time.time()),
    }
    db['items'].append(item)
    save_db(db)

    return jsonify({'message': 'Official media stored.', 'item': item})


@app.route('/compare-media', methods=['POST'])
def compare_media():
    if 'file' not in request.files:
        return jsonify({'error': 'Missing file upload.'}), 400

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400

    dest_dir = os.path.join(UPLOAD_DIR, 'query')
    dest_path = save_uploaded_file(uploaded_file, dest_dir, prefix=str(uuid.uuid4()))

    try:
        query_fp, media_type = fingerprint_media(dest_path, fps=1)
    except Exception as exc:
        return jsonify({'error': 'Failed to fingerprint query media.', 'details': str(exc)}), 500

    db = load_db()
    if not db['items']:
        return jsonify({'error': 'No official media items stored yet.'}), 404

    results = match_fingerprints(query_fp, db['items'], top_k=5)
    return jsonify({'matches': results, 'query_media_type': media_type})


@app.route('/official-media', methods=['GET'])
def official_media():
    db = load_db()
    return jsonify({'items': db['items']})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
