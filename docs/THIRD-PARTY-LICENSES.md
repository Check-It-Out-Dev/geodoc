# geodoc — open-source components and their licences

geodoc is released under the MIT licence (the `LICENSE` file in the root directory),
© 2026 Norbert Marchewka. It uses the open-source components listed below;
all of them are under permissive licences (MIT, Apache 2.0, BSD-3, PSF,
SIL OFL) and impose no obligations on geodoc's licence beyond preserving the
notices below. Of these components the repository itself contains only the
fonts (`app/czcionki/`, with the full OFL texts beside them); the rest is
installed by `pip`, `tools/fetch_runtime.py` or the installer.

| Component | Role | Licence | Copyright |
|---|---|---|---|
| Qwen3-30B-A3B-Instruct-2507 | language model (both roles) | Apache 2.0 | © Alibaba Cloud / Qwen Team |
| llama.cpp (llama-server) | inference engine | MIT | © Georgi Gerganov and contributors |
| pypdfium2 + PDFium | PDF reading and rasterisation | BSD-3 / Apache 2.0 | © Google LLC, PDFium authors; © pypdfium2-team |
| RapidOCR + PP-OCR models | OCR of scanned pages | Apache 2.0 | © RapidAI, © PaddlePaddle Authors |
| ONNX Runtime | execution of the OCR models | MIT | © Microsoft Corporation |
| OnnxTR | OCR layout detection | Apache 2.0 | © OnnxTR contributors |
| openpyxl | writing Excel files | MIT | © openpyxl contributors |
| Pillow | page images for OCR | MIT-CMU (HPND) | © Jeffrey A. Clark and contributors, © Secret Labs AB, © Fredrik Lundh |
| Python 3.12 (embeddable) + standard library | runtime environment | PSF License 2.0 | © Python Software Foundation |
| tray-icon, tao, open (Rust) | system tray icon | MIT / Apache 2.0 | © Tauri Programme within The Commons Conservancy and contributors |
| IBM Plex Sans | interface typeface | SIL OFL 1.1 (Reserved Font Name "Plex") | © IBM Corp. |
| JetBrains Mono | data typeface | SIL OFL 1.1 | © The JetBrains Mono Project Authors |
| Półtawski Nowy | heading typeface | SIL OFL 1.1 | © The Poltawski Nowy Project Authors (revival of Antykwa Półtawskiego) |

**Developer tools only** (`requirements-dev.txt`, never in the product
or in the installer): PyMuPDF (AGPL-3.0) generates synthetic test PDFs,
Augraphy (MIT) degrades them into a "bad scan".
The product reads PDFs exclusively through pypdfium2 (`app/pdfpages.py`).

The installer was built with Inno Setup (© Jordan Russell, Martijn
Laan) — the Inno Setup licence permits free distribution of the
installers created with it; Inno Setup is not part of the application.

## Modifications

The Qwen3 model is used in a form quantised to the GGUF format
(Q4_K_M) — this is a modification within the meaning of §4(b) of the Apache 2.0 licence.
The quantisation was performed by the unsloth team (file from the repository
https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF, sha256
pinned in `installer/manifesty/pack-lekki.json`); geodoc downloads it
(`tools/fetch_runtime.py`) or bundles it with the installer unchanged. Source
weights: https://huggingface.co/Qwen. The weights are not trained or
fine-tuned (frozen-weights law: adaptation exclusively through instructions
and contexts).

The names "Qwen", "Alibaba", "IBM", "JetBrains", "Google", "Microsoft"
are trademarks of their owners and appear here for descriptive purposes only — none
of the entities listed endorses or supports geodoc.

## Licence texts

### Apache License 2.0 (Qwen3, RapidOCR, PP-OCR, OnnxTR, part of pypdfium2)

Full text: https://www.apache.org/licenses/LICENSE-2.0

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
    implied. See the License for the specific language governing
    permissions and limitations under the License.

### MIT License (llama.cpp, ONNX Runtime, openpyxl, Rust libraries)

    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions: The above copyright notice and this
    permission notice shall be included in all copies or substantial
    portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT
    WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
    TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
    PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
    COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
    OR OTHER DEALINGS IN THE SOFTWARE.

### BSD 3-Clause (PDFium)

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met: (1) redistributions of source code must retain the above
    copyright notice, this list of conditions and the following
    disclaimer; (2) redistributions in binary form must reproduce the
    above copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided with
    the distribution; (3) neither the name of the copyright holder nor
    the names of its contributors may be used to endorse or promote
    products derived from this software without specific prior written
    permission. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
    CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES ARE
    DISCLAIMED.

### SIL Open Font License 1.1 (IBM Plex Sans, JetBrains Mono, Półtawski Nowy)

The full texts with the copyright notices sit next to the font files:
`app/czcionki/OFL-IBM-Plex.txt`, `app/czcionki/OFL-JetBrains-Mono.txt`,
`app/czcionki/OFL-Poltawski-Nowy.txt`. The fonts may be used, studied,
modified and redistributed freely, provided they are not sold
on their own and they retain the copyright notices.

### Python Software Foundation License 2.0 (Python 3.12)

Full text: https://docs.python.org/3/license.html
