import base64
import json
import os
import urllib.request
from datetime import date

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


def is_disabled_today(config):
    today = date.today().isoformat()
    for r in config.get("disabled_ranges", []):
        if r["start"] <= today <= r["end"]:
            return True
    return False


def write_status(send: bool):
    with open("send_today.json", "w") as f:
        json.dump({"send": send, "date": date.today().isoformat()}, f)


def generate_scene_prompt(client):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": (
                "You generate prompts for DALL-E 3 to create a funny meme image.\n\n"
                "The meme always has the same setup: two characters, one physically "
                "overpowering/dominating the other. No text, labels, or speech bubbles "
                "of any kind should appear in the image.\n"
                "- The DOMINANT character must be positioned on the LEFT side of the image\n"
                "- The OVERWHELMED character must be positioned on the RIGHT side of the image\n"
                "Both characters must be clearly visible and not obscured.\n\n"
                "Each time, invent a completely new random combination of:\n"
                "- Art style (e.g. renaissance oil painting, 1990s anime, pixel art, watercolor, "
                "noir comic, children's book illustration, Soviet propaganda poster, etc.)\n"
                "- Setting (e.g. underwater tea party, medieval jousting tournament, Wall Street "
                "trading floor, outer space, ancient Roman colosseum, a Costco, etc.)\n"
                "- Character types that fit the setting\n\n"
                "Write only the DALL-E image prompt, nothing else. Be specific and vivid."
            )
        }]
    )
    return response.choices[0].message.content


def detect_aggressor_side(client, image_path):
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
                {
                    "type": "text",
                    "text": (
                        "In this image, one character is dominating or overpowering another. "
                        "Is the dominant character on the LEFT or RIGHT side of the image? "
                        "Reply with only one word: 'left' or 'right'."
                    ),
                },
            ],
        }],
        max_tokens=10,
    )

    answer = response.choices[0].message.content.strip().lower()
    side = "left" if "left" in answer else "right"
    print(f"Aggressor detected on: {side}")
    return side


def draw_speech_bubbles(img, aggressor_side):
    draw = ImageDraw.Draw(img)
    w, h = img.size

    try:
        font = ImageFont.load_default(size=38)
    except TypeError:
        font = ImageFont.load_default()

    if aggressor_side == "left":
        bubbles = [
            ("GET OUT OF THE\nBALLS EVAN", w // 4),
            ("MY\nPRODUCTIVITY", 3 * w // 4),
        ]
    else:
        bubbles = [
            ("MY\nPRODUCTIVITY", w // 4),
            ("GET OUT OF THE\nBALLS EVAN", 3 * w // 4),
        ]

    padding = 22
    cy = h // 6

    for text, cx in bubbles:
        bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        bx0 = cx - tw // 2 - padding
        by0 = cy - th // 2 - padding
        bx1 = cx + tw // 2 + padding
        by1 = cy + th // 2 + padding

        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill="white", outline="black", width=3)

        tail_tip_y = by1 + 45
        draw.polygon([(cx - 14, by1), (cx + 14, by1), (cx, tail_tip_y)], fill="white")
        draw.line([(cx - 14, by1), (cx, tail_tip_y)], fill="black", width=3)
        draw.line([(cx + 14, by1), (cx, tail_tip_y)], fill="black", width=3)

        draw.multiline_text(
            (cx - tw // 2, cy - th // 2),
            text,
            fill="black",
            font=font,
            align="center",
        )


def main():
    with open("config.json") as f:
        config = json.load(f)

    if is_disabled_today(config):
        print(f"Sending disabled today ({date.today().isoformat()}), skipping.")
        write_status(False)
        return

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("Generating scene prompt...")
    prompt = generate_scene_prompt(client)
    print(f"Prompt: {prompt}\n")

    print("Generating image...")
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    urllib.request.urlretrieve(image_url, "/tmp/meme_raw.png")

    print("Detecting aggressor position...")
    aggressor_side = detect_aggressor_side(client, "/tmp/meme_raw.png")

    img = Image.open("/tmp/meme_raw.png").convert("RGB")
    draw_speech_bubbles(img, aggressor_side)
    img.save("meme.jpg", "JPEG", quality=85)
    print("Saved meme.jpg")

    write_status(True)


if __name__ == "__main__":
    main()
