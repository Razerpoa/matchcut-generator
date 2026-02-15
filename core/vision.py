import os
import logging
import cv2
import numpy as np
import pytesseract
from PIL import Image

def preprocess_for_ocr(img: Image.Image) -> tuple[Image.Image, int]:
    # 1. Convert to Grayscale
    img = img.convert('L')

    # 2. Upscale the image (2x) - Very important for small web text
    width, height = img.size
    img = img.resize((width * 2, height * 2), resample=Image.Resampling.LANCZOS)

    # 3. Convert to OpenCV format for thresholding
    open_cv_image = np.array(img)

    # 4. Apply Otsu's Thresholding (converts to pure B&W)
    _, thresh = cv2.threshold(open_cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresh), 2 # Return image and the scale factor

def process_ocr_and_crop(image_path: str, search_text: str, output_dir: str = "crops", prefix: str = "match", max_crops: int = 10) -> int:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    original_img = Image.open(image_path)
    processed_img, scale_factor = preprocess_for_ocr(original_img)
    img_width, img_height = processed_img.size

    # config: psm 3 is often better for layouts; psm 11 for sparse text
    # We use image_to_boxes to get character level data
    # Format: char left bottom right top page
    config = '--psm 3' 
    boxes_string = pytesseract.image_to_boxes(processed_img, config=config)

    found_count = 0
    search_text_normalized = search_text.lower().replace(" ", "")
    
    if not boxes_string:
        logging.info(f"No text found in image for '{search_text}'.")
        return 0

    # Parse boxes
    chars = []
    boxes = []
    
    for line in boxes_string.splitlines():
        parts = line.split()
        if len(parts) >= 6:
            char = parts[0]
            # Tesseract coordinates are bottom-left origin
            left = int(parts[1])
            bottom = int(parts[2])
            right = int(parts[3])
            top = int(parts[4])
            
            y1 = img_height - top
            y2 = img_height - bottom
            
            chars.append(char.lower())
            boxes.append((left, y1, right, y2))

    full_text_continuous = "".join(chars)
    
    # Simple search for the sequence
    start_index = 0
    while found_count < max_crops:
        try:
            match_index = full_text_continuous.index(search_text_normalized, start_index)
        except ValueError:
            break
            
        # We found a match starting at match_index
        end_index = match_index + len(search_text_normalized)
        
        # Get bounding box of this sequence
        match_boxes = boxes[match_index:end_index]
        if not match_boxes: 
            start_index = match_index + 1
            continue
            
        # Calculate union box
        min_x = min(b[0] for b in match_boxes)
        min_y = min(b[1] for b in match_boxes)
        max_x = max(b[2] for b in match_boxes)
        max_y = max(b[3] for b in match_boxes)
        
        # Scale back to original image
        x = min_x // scale_factor
        y = min_y // scale_factor
        w = (max_x - min_x) // scale_factor
        h = (max_y - min_y) // scale_factor
        
        # Padding
        pad_h = h * 3 # vertical padding
        pad_w = w * 1 # add some horizontal padding too
        
        left = max(0, x - pad_w)
        top = max(0, y - pad_h)
        right = min(original_img.width, x + w + pad_w)
        bottom = min(original_img.height, y + h + pad_h)
        
        crop_img = original_img.crop((left, top, right, bottom))
        crop_filename = f"{prefix.replace(' ', '_')}_{found_count}.png"
        crop_path = os.path.join(output_dir, crop_filename)
        crop_img.save(crop_path)
        
        logging.info(f"Match found: '{search_text}' at ({x}, {y})")
        found_count += 1
        
        start_index = match_index + len(search_text_normalized)

    if found_count == 0:
        logging.info(f"No reliable matches for '{search_text}'.")
    return found_count
