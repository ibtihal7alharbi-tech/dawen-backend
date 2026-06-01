from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import anthropic
import base64
from typing import List
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

@app.post("/extract")
async def extract_notes(files: List[UploadFile] = File(...)):
    all_notes = []

    for file in files:
        image_data = base64.standard_b64encode(await file.read()).decode("utf-8")
        media_type = file.content_type if file.content_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/jpeg"

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract ONLY the handwritten text from this image. Return the handwritten words only, one note per line, no descriptions, no explanations, no numbering."
                        }
                    ],
                }
            ],
        )

        notes = response.content[0].text.strip()
        all_notes.append(notes)

    return {"notes": all_notes}


@app.post("/export-pdf")
async def export_pdf(data: dict):
    title = data.get("title", "My Notes")
    notes = data.get("notes", [])

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    max_width = width - 160

    def new_page():
        c.showPage()
        c.setFillColor(colors.HexColor("#F5EFE6"))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        return height - 60

    # background
    c.setFillColor(colors.HexColor("#F5EFE6"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # top bar
    c.setFillColor(colors.HexColor("#6D94C5"))
    c.rect(0, height - 10, width, 10, fill=1, stroke=0)

    # title
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(colors.HexColor("#4F252E"))
    c.drawCentredString(width / 2, height - 60, title)

    # line
    c.setStrokeColor(colors.HexColor("#6D94C5"))
    c.setLineWidth(0.8)
    c.line(60, height - 78, width - 60, height - 78)

    y = height - 130
    counter = 1

    for note in notes:
        sentence = " ".join(note.split())
        if not sentence:
            continue

        # wrap text
        lines = simpleSplit(sentence, "Helvetica", 12, max_width)
        card_height = max(42, len(lines) * 20 + 20)

        if y - card_height < 80:
            y = new_page()

        # card
        c.setFillColor(colors.HexColor("#E8DFCA"))
        c.roundRect(50, y - card_height + 10, width - 100, card_height, 10, fill=1, stroke=0)

        # number
        c.setFillColor(colors.HexColor("#6D94C5"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(68, y - 8, f"{counter}.")

        # text lines
        c.setFillColor(colors.HexColor("#4F252E"))
        c.setFont("Helvetica", 12)
        text_y = y - 8
        for line in lines:
            c.drawString(90, text_y, line)
            text_y -= 20

        counter += 1
        y -= card_height + 16

    # bottom bar
    c.setFillColor(colors.HexColor("#6D94C5"))
    c.rect(0, 0, width, 10, fill=1, stroke=0)

    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=notes.pdf"}
    )