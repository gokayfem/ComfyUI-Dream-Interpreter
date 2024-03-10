import sys
from os import path

sys.path.insert(0, path.dirname(__file__))
from folder_paths import get_save_image_path, get_output_directory
from PIL import Image
import numpy as np

class DreamViewer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dream_interpretation": ("STRING", {"multiline": True, "default": "", "forceInput": True}),
                "hdri_image": ("IMAGE",),
            }
        }

    def __init__(self):
        self.saved_hdri = []
        self.full_output_folder, self.filename, self.counter, self.subfolder, self.filename_prefix = get_save_image_path("dreamsave", get_output_directory())

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "process_inputs"
    CATEGORY = "DreamViewer"

    def process_inputs(self, dream_interpretation, hdri_image):
        # Assuming hdri_image is a PIL Image object for simplicity
        # In your actual code, you might need to convert from whatever format it's in

        # Here, you might want to somehow utilize the dream interpretation
        # For example, you could overlay text on the HDRI image, or choose images based on the interpretation
        image = hdri_image[0].detach().cpu().numpy()
        image = Image.fromarray(np.clip(255. * image, 0, 255).astype(np.uint8)).convert('RGB')

        # This is a placeholder for whatever logic you'd implement

        return self.display(dream_interpretation, image)

    def display(self, dream_interpretation, hdri_image):
        # Save the HDRI image and potentially the interpretation
        filename_with_counter = f"{self.filename}_{self.counter:05}.png"
        image_file = path.join(self.full_output_folder, filename_with_counter)
        hdri_image.save(image_file)

        self.saved_hdri.append({
            "filename": filename_with_counter,
            "subfolder": self.subfolder,
            "type": "output",
            "dream_interpretation": dream_interpretation  # You might want to save the interpretation too
        })

        return {"ui": {"hdri_image": self.saved_hdri, "dream_interpretation": [dream_interpretation]}}
    
NODE_CLASS_MAPPINGS = {
    "DreamViewer": DreamViewer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DreamViewer": "Dream Viewer",
}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
