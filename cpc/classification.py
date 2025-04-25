import numpy as np
from PIL import Image
from tflite_runtime.interpreter import Interpreter

# Define the inference function
def classify_image(image_path):
    # Load the TFLite model and allocate tensors
    model_path = "garbage_classification_quantized_model.tflite"
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()

    # Get input and output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    input_shape = input_details[0]['shape']
    print(f"Model input shape: {input_shape}")

    # Preprocess the image
    IMAGE_WIDTH = input_shape[1]
    IMAGE_HEIGHT = input_shape[2]
    
    # Load and crop the image to center 65%
    img = Image.open(image_path).convert('RGB')
    width, height = img.size
    crop_width = int(width * 0.65)
    crop_height = int(height * 0.65)
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    right = left + crop_width
    bottom = top + crop_height
    img = img.crop((left, top, right, bottom))

    # Resize and normalize
    img = img.resize((IMAGE_WIDTH, IMAGE_HEIGHT))
    
    # Save the post-processed image
    img.save("cropped.jpg")
    print("Post-processed image saved as cropped.jpg")
    
    img_array = np.array(img, dtype=np.float32)
    img_array = img_array / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    # Set input tensor
    interpreter.set_tensor(input_details[0]['index'], img_array)

    # Run the inference
    print("Running inference...")
    interpreter.invoke()

    # Get the output tensor
    output_data = interpreter.get_tensor(output_details[0]['index'])
    results = np.squeeze(output_data)

    # Define categories
    categories = [
        'battery',
        'biological',
        'brown-glass',
        'cardboard',
        'clothes',
        'green-glass',
        'metal',
        'paper',
        'plastic',
        'shoes',
        'trash',
        'white-glass'
    ]
    
    # Mapping to primary categories
    category_mapping = {
        'paper': ['paper', 'cardboard'],
        'metal': ['metal', 'battery'],
        'plastic': ['plastic'],
        'trash': ['biological', 'brown-glass', 'clothes', 'green-glass', 'shoes', 'trash', 'white-glass']
    }

    # Combine probabilities
    category_scores = {'paper': 0.0, 'metal': 0.0, 'plastic': 0.0, 'trash': 0.0}
    for i, class_name in enumerate(categories):
        for category, classes in category_mapping.items():
            if class_name in classes:
                category_scores[category] += results[i]
                break

    # Pick the best category
    top_category = max(category_scores, key=category_scores.get)
    top_score = category_scores[top_category]
    
    threshold = 0.3
    if top_score < threshold:
        top_category = 'trash'

    # Print detailed results
    print("\n--- DETAILED CLASS RESULTS ---")
    sorted_indices = np.argsort(results)[::-1]
    for i in sorted_indices:
        if i < len(categories):
            print(f"{categories[i]}: {results[i]:.4f}")

    print("\n--- CATEGORY RESULTS ---")
    for category in category_scores:
        print(f"{category}: {category_scores[category]:.4f}")

    top_class_idx = np.argmax(results)
    print(f"\nTop detailed class: {categories[top_class_idx]} ({results[top_class_idx]:.4f})")
    print(f"Final category: {top_category} ({category_scores[top_category]:.4f})")

    return top_category