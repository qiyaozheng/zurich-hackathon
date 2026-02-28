import cv2
import numpy as np

# ==========================================
# 1. CONFIGURATION (UPDATE THESE!)
# ==========================================
# Number of INNER corners (where the black squares touch). 
# A standard 10x7 square board has 9x6 inner corners.
CHECKERBOARD = (5, 4) 

# The exact physical size of ONE square on your printed board in meters.
# Example: 25mm = 0.025
SQUARE_SIZE_METERS = 0.025 

# Your working camera index
CAMERA_INDEX = 4 

# ==========================================
# 2. SETUP ARRAYS
# ==========================================
# Prepare the 3D real-world coordinates of the checkerboard corners
# Example: (0,0,0), (0.025,0,0), (0.05,0,0) ...
objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE_METERS

# Arrays to store object points and image points from all captured frames
objpoints = [] # 3D points in real world space
imgpoints = [] # 2D points in image plane

# ==========================================
# 3. START CAMERA
# ==========================================
print(f"Opening camera at /dev/video{CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

if not cap.isOpened():
    print("❌ Failed to open camera. Exiting.")
    exit()

print("\n--- CAMERA CALIBRATION STARTED ---")
print("1. Hold the checkerboard in front of the camera so it is fully visible.")
print("2. Press 'c' to capture a pose. (Aim for 20 to 30 captures).")
print("3. Press 'q' when you are done to calculate the matrix.")

captured_frames = 0
# Termination criteria for refining corner coordinates (sub-pixel accuracy)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Find the chess board corners
        ret_corners, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

        # Create a copy of the frame for drawing so we don't mess up the raw data
        display_frame = frame.copy()

        if ret_corners:
            # Refine corner pixel locations for mathematical accuracy
            corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            
            # Draw the colored rainbow lines on the board
            cv2.drawChessboardCorners(display_frame, CHECKERBOARD, corners_subpix, ret_corners)
            
            cv2.putText(display_frame, "BOARD DETECTED - Press 'c' to capture", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, "Searching for board...", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Show capture count
        cv2.putText(display_frame, f"Captured: {captured_frames} / 20+", (20, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imshow('Intrinsic Calibration', display_frame)
        key = cv2.waitKey(1) & 0xFF

        # --- CAPTURE LOGIC ---
        if key == ord('c'):
            if ret_corners:
                objpoints.append(objp)
                imgpoints.append(corners_subpix)
                captured_frames += 1
                print(f"✅ Captured frame {captured_frames}!")
                
                # Flash the screen white briefly to show a picture was taken
                flash = np.ones(display_frame.shape, dtype=np.uint8) * 255
                cv2.imshow('Intrinsic Calibration', flash)
                cv2.waitKey(100) 
            else:
                print("❌ Cannot capture: Whole board is not clearly visible.")
                
        elif key == ord('q'):
            print("\nFinishing capture phase...")
            break

finally:
    cap.release()
    cv2.destroyAllWindows()

# ==========================================
# 4. CALCULATE CALIBRATION MATRICES
# ==========================================
if captured_frames >= 10: 
    print(f"\nCalculating intrinsics using {captured_frames} images. Please wait...")
    
    # Calculate the camera matrix, distortion coefficients, rotation, and translation vectors
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None
    )

    print("\n================ CALIBRATION SUCCESSFUL ================")
    print("\n1. Camera Matrix (mtx):\n", mtx)
    print("\n2. Distortion Coefficients (dist):\n", dist)
    
    # Calculate Reprojection Error (Closer to 0 is better, anything under 1.0 is good)
    mean_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
        mean_error += error
    
    total_error = mean_error / len(objpoints)
    print(f"\nReprojection Error: {total_error:.4f} pixels")
    if total_error < 1.0:
        print("✅ This is a good calibration!")
    else:
        print("⚠️ High error. You might want to redo it with more varied angles.")

    # Save to file
    filename = "usb_camera_intrinsics.npz"
    np.savez(filename, mtx=mtx, dist=dist)
    print(f"\n💾 Matrices successfully saved to '{filename}'")
    print("========================================================")
else:
    print(f"\n⚠️ Not enough frames captured ({captured_frames}). You need at least 10, ideally 20+.")