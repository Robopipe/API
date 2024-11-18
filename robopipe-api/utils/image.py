import av
import depthai as dai
from PIL import Image


def dai_image_to_pil_image(
    dai_image: dai.ImgFrame, format: str = "nv12"
) -> Image.Image:
    nv12_frame = av.VideoFrame.from_ndarray(dai_image.getFrame(), format)

    return nv12_frame.to_image()
