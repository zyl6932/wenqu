"""
文档解析层 — 模仿 RAGFlow DeepDoc 的分层解析
支持 .txt .md .docx .pptx .pdf .png .jpg
"""
import base64
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .config import STORAGE_CFG, VISION_CFG

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


# ── DOCX ────────────────────────────────────────────
def read_docx(path: str) -> str:
    """解析 .docx，支持表格文本提取"""
    NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with zipfile.ZipFile(path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    paragraphs = []
    for p in root.iter(f"{{{NS}}}p"):
        parts = []
        for elem in p.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "t" and elem.text:
                parts.append(elem.text)
            elif tag == "br":
                parts.append("\n")
            elif tag == "tab":
                parts.append("\t")
        text = "".join(parts)
        if text.strip():
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


# ── PPTX ────────────────────────────────────────────
def read_pptx(path: str) -> str:
    NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    with zipfile.ZipFile(path) as z:
        slides = sorted(
            [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")],
            key=lambda n: int(re.search(r"slide(\d+)", n).group(1)),
        )  # type: ignore
        all_text = []
        for slide_name in slides:
            xml_bytes = z.read(slide_name)
            root = ElementTree.fromstring(xml_bytes)
            texts = []
            for t in root.iter(f"{{{NS_A}}}t"):
                if t.text:
                    texts.append(t.text)
            slide_text = "".join(texts).strip()
            if slide_text:
                all_text.append(slide_text)
    return "\n\n".join(all_text)


# ── PDF ─────────────────────────────────────────────
def read_pdf(path: str) -> str:
    if not HAS_PYPDF:
        raise ImportError("需要 pypdf: pip install pypdf")
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


# ── 图片描述（Ollama 视觉模型）─────────────────────
def describe_image(path: str) -> str:
    with open(path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    import json, urllib.request
    prompt = "请用中文详细描述这张图片的内容，包括：图中展示的信息、数据、图表类型、文字标注、流程步骤等。如果是文档截图，请提取其中的文字。"
    data = {
        "model": VISION_CFG.model,
        "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
        "stream": False,
    }
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"http://localhost:11434/api/chat", data=body)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["message"]["content"]


def extract_pdf_images(pdf_path: str) -> list[str]:
    """提取 PDF 中的图片并用视觉模型描述"""
    if not HAS_PYPDF:
        return []
    try:
        reader = PdfReader(pdf_path)
        descriptions = []
        for page_num, page in enumerate(reader.pages):
            if "/XObject" not in (page.get("/Resources") or {}):
                continue
            xobjects = page["/Resources"]["/XObject"].get_object()
            for obj_name in xobjects:
                xobj = xobjects[obj_name].get_object()
                if xobj.get("/Subtype") == "/Image":
                    width = xobj.get("/Width", 0)
                    height = xobj.get("/Height", 0)
                    if width < 50 or height < 50:
                        continue
                    try:
                        import io
                        from PIL import Image
                        img_data = xobj.get_data()
                        img = Image.open(io.BytesIO(img_data))
                        tmp_path = STORAGE_CFG.data_dir / f"_tmp_img_{page_num}_{obj_name}.png"
                        img.save(str(tmp_path))
                        desc = describe_image(str(tmp_path))
                        descriptions.append(f"[图片 - 第{page_num+1}页] {desc}")
                        tmp_path.unlink()
                    except Exception:
                        continue
        return descriptions
    except Exception:
        return []


# ── 文件识别 ────────────────────────────────────────
def parse_file(filepath: str) -> str:
    """统一入口：根据后缀解析文档"""
    fp = Path(filepath)
    suffix = fp.suffix.lower()
    if suffix == ".docx":
        return read_docx(filepath)
    elif suffix == ".pptx":
        return read_pptx(filepath)
    elif suffix == ".pdf":
        text = read_pdf(filepath)
        try:
            img_descs = extract_pdf_images(filepath)
            if img_descs:
                text += "\n\n" + "\n\n".join(img_descs)
        except Exception:
            pass
        return text
    elif suffix == ".doc":
        raise ValueError(f"旧版 .doc 格式不支持，请转换为 .docx：{fp.name}")
    elif suffix in IMAGE_FORMATS:
        return describe_image(filepath)
    else:
        return fp.read_text(encoding="utf-8")
