# geodoc — G10 degradation fixture: the golden wykaz page put through a
# REPRODUCIBLE Augraphy "bad photocopy" pipeline (fixed seed). Output feeds
# the digit-error-rate regression: OCR quality on clean prints is table
# stakes; the gate is how gracefully it degrades and whether flags fire.
#
# Usage: python tools/degrade_scan.py   -> testdata/wykaz_degraded.png

import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))

SEED = 20260805


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    from pdfpages import render_page
    import cv2
    from augraphy import (AugraphyPipeline, InkBleed, LowInkRandomLines,
                          NoiseTexturize, Jpeg)

    src_png = os.path.join(ROOT, "testdata", "wykaz_clean_tmp.png")
    render_page(os.path.join(ROOT, "testdata", "operat_scan.pdf"), 3, src_png)
    img = cv2.imread(src_png)

    pipeline = AugraphyPipeline(
        ink_phase=[InkBleed(intensity_range=(0.2, 0.3), kernel_size=(3, 3)),
                   LowInkRandomLines(count_range=(3, 6))],
        paper_phase=[NoiseTexturize(sigma_range=(4, 7),
                                    turbulence_range=(3, 5))],
        post_phase=[Jpeg(quality_range=(35, 45))])
    out = pipeline(img)
    dst = os.path.join(ROOT, "testdata", "wykaz_degraded.png")
    cv2.imwrite(dst, out)
    os.remove(src_png)
    print(f"degraded fixture: {dst} ({os.path.getsize(dst) / 1e3:.0f} kB, "
          f"seed {SEED})")


if __name__ == "__main__":
    main()
