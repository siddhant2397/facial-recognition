import streamlit as st
import numpy as np
from PIL import Image
import pymongo
import cv2
from tensorflow import keras
import mtcnn
from sklearn.preprocessing import Normalizer
from scipy.spatial.distance import cosine
from keras_facenet import FaceNet

def face_recognition_model():
    model = FaceNet()
    return model

model = face_recognition_model()

# --- Setup MongoDB connection ---
mongo_client = pymongo.MongoClient("mongodb+srv://siddhantgoswami2397:KjhSS0HMcd1Km3JP@siddhant.qw1vjzb.mongodb.net/?retryWrites=true&w=majority&appName=Siddhant")
db = mongo_client["FacialRecog"]
people = db["people"]



# --- Helper functions ---

def detect_face_mtcnn(img):
    detector = mtcnn.MTCNN()
    faces = detector.detect_faces(img)
    return faces

def get_face(img, box):
    x1, y1, width, height = box
    x1, y1 = abs(x1), abs(y1)
    x2 = x1 + width
    y2 = y1 + height
    return img[y1:y2, x1:x2]

def normalize_img(img):
    mean, std = img.mean(), img.std()
    return (img - mean) / std

def get_emb(face):
    face = normalize_img(face)
    face = cv2.resize(face, (160, 160))
    emb = model.embeddings([face])[0]
    return emb

def encode_face(image):
    img = np.array(image.convert('RGB'))
    faces = detect_face_mtcnn(img)
    if not faces:
        return None
    # Choose the biggest face detected
    biggest = max(faces, key=lambda b: b['box'][2]*b['box'][3])
    face = get_face(img, biggest['box'])
    emb = get_emb(face)
    l2 = Normalizer()
    emb = l2.transform(emb.reshape(1, -1))[0]
    return emb

# --- Streamlit UI App ---

st.title("Face Recognition Access Control with Model from Google Drive")

tab1, tab2 = st.tabs(["Enroll New Person", "Authorize Person"])

with tab1:
    st.header("Enroll New Person")
    name = st.text_input("Enter Person's Name")
    uploaded_img = st.file_uploader("Upload Person's Photo", type=['jpg', 'jpeg', 'png'])
    if st.button("Enroll") and name and uploaded_img:
        img = Image.open(uploaded_img)
        emb = encode_face(img)
        if emb is not None:
            # Store embedding and name in MongoDB
            people.insert_one({
                "name": name.strip(),
                "embedding": emb.tolist()
            })
            st.success(f"{name.strip()} enrolled successfully!")
        else:
            st.warning("No face detected in the image. Please upload a clear face image.")

with tab2:
    st.header("Authorize Person")
    test_img = st.file_uploader("Upload Image to Authorize", type=['jpg', 'jpeg', 'png'])
    if st.button("Authorize") and test_img:
        img = Image.open(test_img)
        emb = encode_face(img)
        if emb is not None:
            min_dist = 1.0
            matched_name = "Unknown"
            for person in people.find():
                db_emb = np.array(person['embedding'])
                dist = cosine(emb, db_emb)
                print(f"Comparing with {person['name']} at distance {dist}")
                if dist < 0.5 and dist < min_dist:  # Threshold for face match
                    min_dist = dist
                    matched_name = person['name']
            if matched_name != "Unknown":
                st.success(f"Access Granted! Welcome, {matched_name}.")
            else:
                st.error("Access Denied: Unknown Person.")
        else:
            st.warning("No face detected in the uploaded image.")

