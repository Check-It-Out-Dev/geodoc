# geodoc — raster branch, primary engine: RapidOCR (PP-OCRv6, ONNX, CPU,
# Apache-2.0; ~0.7 s/page measured on this box). Confidence rides with every
# line — the G4 agreement gate (second engine, Tesseract pol) joins later;
# until then low-confidence lines are FLAGGED, never silently trusted.

MIN_CONF = 0.85

_engine = None


def available():
    try:
        import rapidocr  # noqa: F401
        return True
    except ImportError:
        return False


def engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        _engine = RapidOCR()
    return _engine


_engine2 = None


def second_available():
    try:
        import onnxtr  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_page_second(png_path):
    """Second engine for the G4 agreement gate: onnxtr (docTR ONNX, Apache).
    Different detector+recognizer family than RapidOCR — real independence."""
    global _engine2
    from onnxtr.io import DocumentFile
    from onnxtr.models import ocr_predictor
    if _engine2 is None:
        _engine2 = ocr_predictor(det_arch="fast_base",
                                 reco_arch="crnn_vgg16_bn")
    res = _engine2(DocumentFile.from_images(png_path))
    lines = []
    for pg in res.pages:
        for blk in pg.blocks:
            for ln in blk.lines:
                lines.append(" ".join(w.value for w in ln.words))
    return "\n".join(lines)


# 4-7 integer digits: PL-2000/1965 are 7-digit, PL-1992 6-digit, lokalne 4-5
COORD = __import__("re").compile(r"\d{4,7}\.\d{2}")


def coord_agreement(text_a, text_b):
    """G4 unit of agreement = the coordinate string (digit fidelity is the
    product's life). Returns sets: confirmed by both, single-engine, per side."""
    a = set(COORD.findall(text_a or ""))
    b = set(COORD.findall(text_b or ""))
    return dict(obie=sorted(a & b), tylko_pierwszy=sorted(a - b),
                tylko_drugi=sorted(b - a))


def ocr_page(png_path, min_conf=MIN_CONF):
    """One page image -> {lines: [{text, conf, low}], text, mean_conf,
    low_count}. Reading order as detected (top-down for typed documents)."""
    res = engine()(png_path)
    txts = list(getattr(res, "txts", None) or [])
    scores = list(getattr(res, "scores", None) or [])
    boxes = getattr(res, "boxes", None)
    try:
        from PIL import Image
        with Image.open(png_path) as im:  # PIXEL dims of the PNG — OCR boxes
            iw, ih = im.size              # normalize against pixels, not points
    except Exception:
        iw = ih = None
    lines = []
    for i, t in enumerate(txts):
        conf = round(float(scores[i]), 3) if i < len(scores) else None
        box = None
        if boxes is not None and i < len(boxes) and iw:
            pts = boxes[i]
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            box = [round(min(xs) / iw, 4), round(min(ys) / ih, 4),
                   round(max(xs) / iw, 4), round(max(ys) / ih, 4)]
        lines.append(dict(text=t, conf=conf, box=box,
                          low=(conf is not None and conf < min_conf)))
    confs = [l["conf"] for l in lines if l["conf"] is not None]
    return dict(lines=lines,
                text="\n".join(l["text"] for l in lines),
                mean_conf=(round(sum(confs) / len(confs), 3) if confs else None),
                low_count=sum(1 for l in lines if l["low"]))
