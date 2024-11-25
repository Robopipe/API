import av
import depthai as dai
from PIL import Image


class UnsupportedImageFormat(Exception):
    pass


def img_frame_to_pil_image(img_frame: dai.ImgFrame) -> Image.Image:
    img_type = img_frame.getType()

    if img_type == dai.RawImgFrame.Type.RAW8:
        return Image.fromarray(img_frame.getFrame(), "L")
    elif img_type == dai.RawImgFrame.Type.NV12:
        return av.VideoFrame.from_ndarray(img_frame.getFrame(), "nv12").to_image()
    elif img_type == dai.RawImgFrame.Type.BGR888i:
        return Image.fromarray(img_frame.getFrame()[..., ::-1])
    else:
        raise UnsupportedImageFormat(f"Given format: {img_type}")
