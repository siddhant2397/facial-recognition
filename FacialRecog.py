import streamlit as st
from PIL import Image
import requests
import io
import pymongo
import base64
import os
from datetime import datetime, timedelta
import pytz

# --- Azure Face API credentials ---
AZURE_ENDPOINT = "https://siddhant.cognitiveservices.azure.com/"  # e.g. https://<region>.api.cognitive.microsoft.com/
AZURE_KEY = st.secrets["key"]

# --- MongoDB credentials ---

# --- MongoDB setup ---
client = pymongo.MongoClient("mongodb+srv://siddhantgoswami2397:KjhSS0HMcd1Km3JP@siddhant.qw1vjzb.mongodb.net/?retryWrites=true&w=majority&appName=Siddhant")
db = client["FacialRecog"]
col = db["people"]
db1 = client["attendance"]
attendance_col = db["attendance_col"]

def register_face(image_bytes):
    """Detects face and stores image and Azure faceId in MongoDB."""
    url = AZURE_ENDPOINT + "face/v1.0/detect"
    headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Content-Type': 'application/octet-stream'}
    params = {'returnFaceId': 'true'}
    response = requests.post(url, headers=headers, params=params, data=image_bytes)
    faces = response.json()
    if faces and isinstance(faces, list):
        # encode image to base64 to save in MongoDB
        face_id = faces[0]['faceId']
        col.insert_one({"name":name, "number":number,"faceId": face_id})
        return face_id
    st.write(f"No face detected in the image or API response error:{faces}")
    return None

def get_registered_faces():
    """Retrieves all registered faceId and images from MongoDB."""
    return list(col.find({}))

def verify_face(face_id1, face_id2):
    """Uses Azure Face API to verify two faceIds."""
    url = AZURE_ENDPOINT + "face/v1.0/verify"
    headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Content-Type': 'application/json'}
    data = {"faceId1": face_id1, "faceId2": face_id2}
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def get_face_id_from_image(image_bytes):
    """Detect face in image and return faceId."""
    url = AZURE_ENDPOINT + "face/v1.0/detect"
    headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Content-Type': 'application/octet-stream'}
    params = {'returnFaceId': 'true'}
    response = requests.post(url, headers=headers, params=params, data=image_bytes)
    faces = response.json()
    if faces:
        return faces[0]['faceId']
    return None

 #---- Streamlit UI ----
st.title("Face Registration and Verification App")

tab1, tab2, tab3 = st.tabs(["Register Face", "Verify Face", "Attendance Records"])

with tab1:
    st.header("Register Face for Verification")
    name = st.text_input("Enter Name")
    number = st.text_input("Enter Service Number")
    uploaded = st.file_uploader("Upload an image to register", type=["jpg", "jpeg", "png"])
    if uploaded and name and number:
        if st.button("Register Face"):
            image = Image.open(uploaded).convert("RGB")
            st.image(image, caption="Uploaded Image")
            img_bytes_buf = io.BytesIO()
            image.save(img_bytes_buf, format="JPEG")
            face_id = register_face(img_bytes_buf.getvalue())
            if face_id:
                st.success(f"Face registered! Face ID: {face_id}")
            else:
                st.error("No face detected! Try another image.")

    if st.button("Registered Members:"):
        members = get_registered_faces()
        for entry in members:
            st.write(f"**Name:** {entry.get('name', 'N/A')}")
            st.write(f"**Number:** {entry.get('number', 'N/A')}")
            st.markdown("---")

with tab2:
    st.header("Verify Face")
    uploaded_verify = st.file_uploader("Upload an image to verify", type=["jpg", "jpeg", "png"], key="verify_upload")
    if uploaded_verify and not st.session_state.get("verify_done", False):
        image = Image.open(uploaded_verify).convert("RGB")
        st.image(image, caption="Verification Image")
        img_bytes_buf = io.BytesIO()
        image.save(img_bytes_buf, format="JPEG")
        verify_face_id = get_face_id_from_image(img_bytes_buf.getvalue())
        if not verify_face_id:
            st.error("No face found in verification image!")
        else:
            faces = get_registered_faces()
            if not faces:
                st.warning("No registered faces in database.")
            else:
                ist = pytz.timezone('Asia/Kolkata')
                authorized_user = None
                confidence = 0.0
                for entry in faces:
                    match_result = verify_face(verify_face_id, entry['faceId'])
                    isIdentical = match_result.get("isIdentical", False)
                    if isIdentical:
                        authorized_user = entry
                        confidence = match_result.get("confidence", 0)
                        break
                if authorized_user:
                    st.session_state["verify_done"] = True
                    st.session_state["authorized_user"] = authorized_user
                    st.session_state["confidence"] = confidence
                else:
                    st.error("Unauthorized: No matching registered face found.")
if st.session_state.get("verify_done", False):
    authorized_user = st.session_state["authorized_user"]
    confidence = st.session_state["confidence"]
    ist = pytz.timezone('Asia/Kolkata')
    st.success(f"✅ Authorized user: {authorized_user.get('name','N/A')} "
               f"User Number: {authorized_user.get('number', 'N/A')} "
               f"(Confidence: {confidence:.2f})")
    now_ist = datetime.now(ist)
    start_day = datetime.combine(now_ist.date(), time.min).replace(tzinfo=ist)
    end_day = start_day + timedelta(days=1)
    existing_attendance = attendance_col.find_one({"faceId": authorized_user['faceId'],
                                                                       "timestamp": {"$gte": start_day, "$lt": end_day}})
    if existing_attendance:
        st.info(f"Attendance for {authorized_user.get('name','N/A')} already recorded today.")
    else:
        WNumber = st.text_input("Enter your W number (to store with attendance)")
        if st.button("Submit Attendance"):
            if not WNumber.strip():
                st.warning("Please enter your W number before submitting.")
            else:
                attendance_record = {"faceId": authorized_user['faceId'],
                                     "name": authorized_user.get('name', 'N/A'),
                                     "number": authorized_user.get('number', 'N/A'),
                                     "WNumber": WNumber.strip(),
                                     "timestamp": now_ist}
                attendance_col.insert_one(attendance_record)
                st.success(f"Attendance recorded for {authorized_user.get('name','N/A')} at "
                           f"{now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                          )
                st.session_state["verify_done"] = False  # reset                                    
                
with tab3:
    ist = pytz.timezone('Asia/Kolkata')
    st.subheader("Attendance Records")
    records = attendance_col.find().sort("timestamp", -1).limit(200)
    for rec in records:
        ist_time = rec['timestamp']
        st.write(
            f"{rec.get('name', 'N/A')} ({rec.get('number', 'N/A')}) - {ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
