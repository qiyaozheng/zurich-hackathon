import cv2
import os
import json
import numpy as np
from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types
from pydantic import BaseModel

# 1. Load environment variables from the .env file
load_dotenv()

# The client will automatically look for the GEMINI_API_KEY environment variable
client = genai.Client()

# 2. Define our structured output
class PartInfo(BaseModel):
    part_type: str
    detected_text: str

class ImageAnalysis(BaseModel):
    parts: list[PartInfo]

# 3. Apply your Calibration Parameters
mtx = np.array([[7.43979721e+03, 0.00000000e+00, 1.10337352e+03],
                [0.00000000e+00, 7.38832199e+03, 8.10731785e+02],
                [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]])

dist = np.array([[[-0.72200534, -0.08970809, -0.03362853, -0.01038592,  1.48548678]]])

# 4. Initialize Camera
cap = cv2.VideoCapture(4)

print("Starting camera... Press 'Space' to run OCR, or 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Undistort the frame using your calibration data
    # This ensures straight lines are straight and text isn't warped!
    undistorted_frame = cv2.undistort(frame, mtx, dist, None, mtx)

    # Show the corrected feed
    cv2.imshow("Calibrated Part Inspector", undistorted_frame)
    key = cv2.waitKey(1) & 0xFF

    # 5. Trigger OCR on Spacebar press
    if key == 32: 
        print("\nCapturing image and sending to Gemini API...")
        
        # Use the undistorted frame for processing
        rgb_frame = cv2.cvtColor(undistorted_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        prompt = """
        Analyze this undistorted image. Identify any objects, parts, or components.
        Extract and read all visible text, serial numbers, or labels accurately.
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash', # Or gemini-1.5-flash depending on your tier availability
                contents=[pil_image, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ImageAnalysis,
                    temperature=0.0 # Force maximum determinism for OCR
                ),
            )
            
            results = json.loads(response.text)
            print("--- OCR & Detection Results ---")
            for part in results.get('parts', []):
                print(f"Object Type: {part.get('part_type')}")
                print(f"Read Text:   {part.get('detected_text')}")
                print("-" * 30)
                
        except Exception as e:
            print(f"Error during API call: {e}")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()