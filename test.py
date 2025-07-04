from ultralytics import YOLO
import cv2
import matplotlib.pyplot as plt

# Load your YOLOv11 model (replace with your path if needed)
model = YOLO("runs/train/yolo11_custom/weights/best.pt")  # Update this path if needed

# Load the image
image_path = "query/clipperMulti.jpg"  # Change to your image path
image = cv2.imread(image_path)
image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# Run inference
results = model(image_rgb)

# Visualize results
annotated_image = results[0].plot()

# Show using matplotlib
plt.imshow(annotated_image)
plt.axis("off")
plt.title("YOLOv11 Detection")
plt.show()

# Optionally save the result
cv2.imwrite("result.jpg", annotated_image)
