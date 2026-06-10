import base64
import json
import os
import random
from datetime import date

from openai import OpenAI
from PIL import Image


def load_art_styles(path="art_styles.txt"):
    with open(path) as f:
        styles = []
        for line in f:
            line = line.strip()
            if line:
                # Strip leading "NNN. " numbering
                parts = line.split(". ", 1)
                styles.append(parts[1] if len(parts) == 2 else parts[0])
    return styles


def is_disabled_today(config):
    today = date.today().isoformat()
    for r in config.get("disabled_ranges", []):
        if r["start"] <= today <= r["end"]:
            return True
    return False


def write_status(send: bool):
    with open("send_today.json", "w") as f:
        json.dump({"send": send, "date": date.today().isoformat()}, f)


def generate_scene_prompt(client, art_style):
    with open("reference.png", "rb") as f:
        ref_image = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{ref_image}"},
                },
                {
                    "type": "text",
                    "text": (
                        "You generate prompts for DALL-E 3 to create a funny meme image.\n\n"
                        "Use the image above as a reference for the composition and layout only — "
                        "two characters, the dominant one on the left and the overwhelmed one on the right.\n\n"
                        "The meme always has the same setup: two characters, one physically "
                        "dominating/overpowering the other. The overpowered character needs to look very scared, overwhelmed, or tired. They should be inside of a ball or near a ball of any kind.\n"
                        "- The dominant character has a speech bubble pointing directly at them "
                        "that says EXACTLY: \"GET OUT OF THE BALLS EVAN\"\n"
                        "- The overwhelmed character has a speech bubble pointing directly at them "
                        "that says EXACTLY: \"MY PRODUCTIVITY\"\n"
                        "Both speech bubbles must be white with black text, clearly legible, large "
                        "enough to read easily, and each bubble's tail must point unambiguously to "
                        "its speaker. Place the characters on opposite sides of the image so the "
                        "bubbles do not overlap.\n\n"
                        f"The art style MUST be: {art_style}\n\n"
                        "Invent a completely new random combination of:\n"
                        "- Setting (e.g. underwater tea party, medieval jousting tournament, Wall Street "
                        "trading floor, outer space, ancient Roman colosseum, a Costco, etc.)\n"
                        "- Character types that fit the setting and art style\n\n"
                        "Write only the DALL-E image prompt, nothing else. Be specific and vivid."
                    ),
                },
            ],
        }]
    )
    return response.choices[0].message.content


def main():
    with open("config.json") as f:
        config = json.load(f)

    if is_disabled_today(config):
        print(f"Sending disabled today ({date.today().isoformat()}), skipping.")
        write_status(False)
        return

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    art_styles = load_art_styles()
    art_style = random.choice(art_styles)
    print(f"Art style: {art_style}")

    print("Generating scene prompt...")
    prompt = generate_scene_prompt(client, art_style)
    print(f"Prompt: {prompt}\n")

    print("Generating image...")
    response = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )

    image_data = base64.b64decode(response.data[0].b64_json)
    with open("/tmp/meme_raw.png", "wb") as f:
        f.write(image_data)

    img = Image.open("/tmp/meme_raw.png").convert("RGB")
    img.save("meme.jpg", "JPEG", quality=85)
    print("Saved meme.jpg")

    write_status(True)


if __name__ == "__main__":
    main()
