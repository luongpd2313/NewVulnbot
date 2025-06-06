from typing import List

import cv2
import numpy as np
import tqdm
from langchain_community.document_loaders.unstructured import UnstructuredFileLoader
from PIL import Image

from rag.parsers.ocr import get_ocr


class RapidOCRPDFLoader(UnstructuredFileLoader):
    def __init__(self, file_path:str, **kwargs):
        kwargs.setdefault("unstructured_kwargs", {"strategy": "fast"})
        super().__init__(file_path, **kwargs)

    def _get_elements(self) -> List:
        def rotate_img(img, angle):

            h, w = img.shape[:2]
            rotate_center = (w / 2, h / 2)

            M = cv2.getRotationMatrix2D(rotate_center, angle, 1.0)
            # 计算图像新边界
            new_w = int(h * np.abs(M[0, 1]) + w * np.abs(M[0, 0]))
            new_h = int(h * np.abs(M[0, 0]) + w * np.abs(M[0, 1]))
            # 调整旋转矩阵以考虑平移
            M[0, 2] += (new_w - w) / 2
            M[1, 2] += (new_h - h) / 2

            rotated_img = cv2.warpAffine(img, M, (new_w, new_h))
            return rotated_img

        def pdf2text(filepath):
            import fitz  # pyMuPDF里面的fitz包，不要与pip install fitz混淆
            import numpy as np

            print(f"*****filepath in pdf parser: {filepath}***")
            ocr = get_ocr()
            doc = fitz.open(filepath)
            resp = ""

            b_unit = tqdm.tqdm(
                total=doc.page_count, desc="RapidOCRPDFLoader context page index: 0"
            )
            for i, page in enumerate(doc):
                b_unit.set_description(
                    "RapidOCRPDFLoader context page index: {}".format(i)
                )
                b_unit.refresh()
                text = page.get_text("")
                resp += text + "\n"

                img_list = page.get_image_info(xrefs=True)
                for img in img_list:
                    if xref := img.get("xref"):
                        bbox = img["bbox"]

                        if (bbox[2] - bbox[0]) / (page.rect.width) < 0.6 or (bbox[3] - bbox[1]) / (
                            page.rect.height
                        ) < 0.6:
                            continue
                        pix = fitz.Pixmap(doc, xref)
                        samples = pix.samples
                        if int(page.rotation) != 0:
                            img_array = np.frombuffer(
                                pix.samples, dtype=np.uint8
                            ).reshape(pix.height, pix.width, -1)
                            tmp_img = Image.fromarray(img_array)
                            ori_img = cv2.cvtColor(np.array(tmp_img), cv2.COLOR_RGB2BGR)
                            rot_img = rotate_img(img=ori_img, angle=360 - page.rotation)
                            img_array = cv2.cvtColor(rot_img, cv2.COLOR_RGB2BGR)
                        else:
                            img_array = np.frombuffer(
                                pix.samples, dtype=np.uint8
                            ).reshape(pix.height, pix.width, -1)

                        result, _ = ocr(img_array)
                        if result:
                            ocr_result = [line[1] for line in result]
                            resp += "\n".join(ocr_result)

                b_unit.update(1)

            print(f"----------resp in pdf parser: {resp}--------")
            return resp

        text = pdf2text(self.file_path)
        print(f"----Unstructured kwargs: {self.unstructured_kwargs}-----")
        from unstructured.partition.text import partition_text

        return partition_text(text=text, **self.unstructured_kwargs)

# from langchain.docstore.document import Document

# class RapidOCRPDFLoader:
#     def __init__(self, file_path:str, **kwargs):
#         self.file_path = file_path
#         # kwargs.setdefault("unstructured_kwargs", {"strategy": "fast"})

#     def load(sefl) -> List[Document]:
#         print(f"Loading PDF from: {self.file_path}")
#         text = self._pdf2text()
#         print(f"Extracted text preview: {text[:101]}....")
#         return [Document(page_content=text)]

#     def _pdf2text(self) -> str:
#         def rotate_img(img, angle):
#             h, w = img.shape[:2]
#             rotate_center = (w / 2, h / 2)

#             M = cv2.getRotationMatrix2D(rotate_center, angle, 1.0)
#             # 计算图像新边界
#             new_w = int(h * np.abs(M[0, 1]) + w * np.abs(M[0, 0]))
#             new_h = int(h * np.abs(M[0, 0]) + w * np.abs(M[0, 1]))
#             # 调整旋转矩阵以考虑平移
#             M[0, 2] += (new_w - w) / 2
#             M[1, 2] += (new_h - h) / 2

#             rotated_img = cv2.warpAffine(img, M, (new_w, new_h))
#             return rotated_img
        
#             import fitz  # pyMuPDF里面的fitz包，不要与pip install fitz混淆
#             import numpy as np

#             print(f"*****filepath in pdf parser: {filepath}***")
#             ocr = get_ocr()
#             doc = fitz.open(filepath)
#             resp = ""

#             b_unit = tqdm.tqdm(
#                 total=doc.page_count, desc="RapidOCRPDFLoader context page index: 0"
#             )
#             for i, page in enumerate(doc):
#                 b_unit.set_description(
#                     "RapidOCRPDFLoader context page index: {}".format(i)
#                 )
#                 b_unit.refresh()
#                 text = page.get_text("")
#                 resp += text + "\n"

#                 img_list = page.get_image_info(xrefs=True)
#                 for img in img_list:
#                     if xref := img.get("xref"):
#                         bbox = img["bbox"]

#                         if (bbox[2] - bbox[0]) / (page.rect.width) < 0.6 or (bbox[3] - bbox[1]) / (
#                             page.rect.height
#                         ) < 0.6:
#                             continue
#                         pix = fitz.Pixmap(doc, xref)
#                         samples = pix.samples
#                         if int(page.rotation) != 0:
#                             img_array = np.frombuffer(
#                                 pix.samples, dtype=np.uint8
#                             ).reshape(pix.height, pix.width, -1)
#                             tmp_img = Image.fromarray(img_array)
#                             ori_img = cv2.cvtColor(np.array(tmp_img), cv2.COLOR_RGB2BGR)
#                             rot_img = rotate_img(img=ori_img, angle=360 - page.rotation)
#                             img_array = cv2.cvtColor(rot_img, cv2.COLOR_RGB2BGR)
#                         else:
#                             img_array = np.frombuffer(
#                                 pix.samples, dtype=np.uint8
#                             ).reshape(pix.height, pix.width, -1)

#                         result, _ = ocr(img_array)
#                         if result:
#                             ocr_result = [line[1] for line in result]
#                             resp += "\n".join(ocr_result)

#                 b_unit.update(1)

#             print(f"----------resp in pdf parser: {resp}--------")
#             return resp

#     def _get_elements(self) -> List:
#         text = self._pdf2text()
#         return [text]