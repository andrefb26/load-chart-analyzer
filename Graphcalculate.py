import cv2
import numpy as np
import pytesseract

import platform
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
class GraphCalculate:
    PAD = 8
    NONWHITE_HI = 240
    MIN_LEN_RATIO = 0.75
    MAX_THICKNESS = 12

    def __init__(self, img_bgr):
        self.img = img_bgr
        self.crop_img = None
        self.bbox = None  # (x1, y1, x2, y2)

    def crop(self):
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        bw = cv2.inRange(gray, 0, self.NONWHITE_HI)

        h, w = bw.shape
        k = max(25, w // 25)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
        lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)

        cnts, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in cnts:
            x, y, cw, ch = cv2.boundingRect(c)
            if cw >= self.MIN_LEN_RATIO * w and ch <= self.MAX_THICKNESS:
                candidates.append((x, y, cw, ch))

        if not candidates:
            raise ValueError("Não encontrei linhas horizontais longas (grelha/eixo).")

        baseline = max(candidates, key=lambda r: r[1])
        top_line = min(candidates, key=lambda r: r[1])

        x0, y0, w0, h0 = baseline
        xt, yt, wt, ht = top_line

        x1 = max(0, min(x0, xt) - self.PAD)
        x2 = min(self.img.shape[1] - 1, max(x0 + w0, xt + wt) + self.PAD)
        y1 = 0
        y2 = min(self.img.shape[0] - 1, y0 + h0 + self.PAD)

        self.bbox = (x1, y1, x2, y2)
        self.crop_img = self.img[y1:y2+1, x1:x2+1]
        return self.crop_img, self.bbox

    def get_scale(self):
        if self.crop_img is None:
            raise ValueError("Primeiro chama crop() para definir self.crop_img.")

        gray = cv2.cvtColor(self.crop_img, cv2.COLOR_BGR2GRAY)
        bw = cv2.inRange(gray, 0, self.NONWHITE_HI)

        h, w = bw.shape
        k = max(25, w // 25)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
        lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)

        cnts, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in cnts:
            x, y, cw, ch = cv2.boundingRect(c)
            if cw >= self.MIN_LEN_RATIO * w and ch <= self.MAX_THICKNESS:
                candidates.append((x, y, cw, ch))

        if len(candidates) < 2:
            raise ValueError("Não encontrei linhas suficientes para calcular a escala.")

        ys = sorted([r[1] for r in candidates])
        diffs = np.diff(ys)
        diffs = diffs[diffs >= 3]
        if len(diffs) == 0:
            raise ValueError("Diferenças entre linhas inválidas (talvez ruído).")

        n_intervals = len(ys) - 1
        step_px = float(ys[-1] - ys[0]) / n_intervals
        y_base = ys[-1]

        return step_px, y_base, ys

    def color_mask_hsv(self, lower, upper):
        if self.crop_img is None:
            raise ValueError("Primeiro chama crop() para definir self.crop_img.")

        hsv = cv2.cvtColor(self.crop_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)

        h, w = mask.shape
        k = max(3, (min(h, w) // 200) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        return mask

    def find_bar_rects(self, mask, min_height_ratio=0.15, max_width_ratio=0.12):
        h, w = mask.shape
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rects = []
        for c in cnts:
            x, y, cw, ch = cv2.boundingRect(c)
            if ch >= int(min_height_ratio * h) and cw <= int(max_width_ratio * w) and cw > 2:
                rects.append((x, y, cw, ch))

        rects.sort(key=lambda r: r[0])
        return rects



    def get_x_labels(self, upscale=4):
        if self.bbox is None:
            raise ValueError("Primeiro chama crop().")

        bx1, by1, bx2, by2 = self.bbox
        img_h = self.img.shape[0]

        if by2 >= img_h - 5:
            print("[OCR] AVISO: sem espaço abaixo do crop para labels.")
            return [], []

        label_strip = self.img[by2:img_h, bx1:bx2]

        enlarged = cv2.resize(label_strip, None, fx=upscale, fy=upscale,
                            interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        angle = 45.0
        ch, cw = binary.shape[:2]
        center = (cw // 2, ch // 2)
        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        cos_a, sin_a = abs(M[0, 0]), abs(M[0, 1])
        new_w = int(ch * sin_a + cw * cos_a)
        new_h = int(ch * cos_a + cw * sin_a)
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        rotated = cv2.warpAffine(binary, M, (new_w, new_h), borderValue=0)

        data = pytesseract.image_to_data(
            rotated,
            config="--psm 11 --oem 3",
            output_type=pytesseract.Output.DICT
        )

        words = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            conf = int(data["conf"][i])
            if text and conf > 20 and len(text) > 1:
                x_center_rot = data["left"][i] + data["width"][i] / 2
                x_orig = (x_center_rot - M[0, 2]) / upscale
                words.append((x_orig, text, conf))

        words.sort(key=lambda t: t[0])

        # Juntar fragmentos próximos (ex: "TrialMRY" + "1_2" → "TrialMRY1_2")
        merged = []
        for x_pos, text, conf in words:
            if merged and (x_pos - merged[-1][0]) < (50 / upscale):
                prev_x, prev_text, prev_conf = merged[-1]
                merged[-1] = [prev_x, prev_text + text, max(prev_conf, conf)]
            else:
                merged.append([x_pos, text, conf])

        x_centers = [ww[0] for ww in merged]
        labels = [self._fix_ocr(ww[1]) for ww in merged]

        return labels, x_centers
    @staticmethod
    def _fix_ocr(text):
        """Corrige erros comuns do OCR em nomes de sensores."""
        fixes = {
            "Trlal": "Trial",
            "Tral":  "Trial",
            "Trtal": "Trial",
            "Triai": "Trial",
        }
        for wrong, right in fixes.items():
            text = text.replace(wrong, right)
        return text