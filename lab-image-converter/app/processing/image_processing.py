import numpy as np
from PIL import Image


def normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    arr = array.astype(np.float64)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    vmin = arr.min()
    vmax = arr.max()

    if vmin == vmax:
        return np.zeros(arr.shape, dtype=np.uint8)

    normalized = (arr - vmin) / (vmax - vmin) * 255.0
    return np.clip(normalized, 0, 255).astype(np.uint8)


def ensure_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        return remove_alpha(image)
    if image.mode in ("L", "LA", "P", "I", "F", "I;16"):
        return image.convert("RGB")
    if image.mode == "RGB":
        return image
    return image.convert("RGB")


def remove_alpha(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image
    background = Image.new("RGB", image.size, (255, 255, 255))
    background.paste(image, mask=image.split()[3])
    return background


def array_to_pil(array: np.ndarray) -> Image.Image:
    if array.dtype != np.uint8:
        array = normalize_to_uint8(array)

    if array.ndim == 2:
        return Image.fromarray(array, mode="L")

    if array.ndim == 3:
        if array.shape[2] == 1:
            return Image.fromarray(array[:, :, 0], mode="L")
        if array.shape[2] == 3:
            return Image.fromarray(array, mode="RGB")
        if array.shape[2] == 4:
            img = Image.fromarray(array, mode="RGBA")
            return remove_alpha(img)
        return Image.fromarray(array[:, :, 0], mode="L")

    raise ValueError(f"Unsupported array shape: {array.shape}")
